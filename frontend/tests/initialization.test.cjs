/* eslint-disable @typescript-eslint/no-require-imports -- Test the real pipeline with controlled network/model dependencies. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const ts = require('typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename);
function pipelineWith(initFaceMesh, loadAffectModel, overrides = {}, context = {}) {
  const filename = path.resolve(__dirname,'../src/lib/ml/pipeline.ts');
  const code = ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  const actualRequire = createRequire(filename);
  const fixtureModule = {exports:{}};
  const requireDependency = name => overrides[name] || (name === './faceMesh' ? {initFaceMesh} : name === './affectScoring' ? {loadAffectModel} : actualRequire(name));
  const run = vm.runInNewContext(`(function(require,module,exports){${code}\n})`, context);
  run(requireDependency,fixtureModule,fixtureModule.exports);
  return new fixtureModule.exports.AttentionPipeline();
}
const tick = () => new Promise(resolve=>setImmediate(resolve));

test('camera initialization completes while affect download is still pending', async () => {
  let completeDownload;
  const download = new Promise(resolve=>{completeDownload=resolve;});
  const pipeline = pipelineWith(async()=>({}),()=>download);
  let initialized=false;
  void pipeline.initialize({}).then(()=>{initialized=true;});
  await tick();
  assert.equal(initialized,true,'slow model loading must not hold calibration');
  assert.equal(pipeline.affectAvailable,false);
  completeDownload(true);
  await tick();
  assert.equal(pipeline.affectAvailable,true);
});

test('failed affect download preserves geometric initialization', async () => {
  const pipeline = pipelineWith(async()=>({}),async()=>{throw new Error('Network stalled');});
  await pipeline.initialize({});
  await tick();
  assert.equal(pipeline.affectAvailable,false);
});

test('face tracker failure remains actionable instead of pretending camera analysis is ready', async () => {
  let affectRequested=false;
  const pipeline=pipelineWith(async()=>{throw new Error('Face tracker failed');},async()=>{affectRequested=true;return true;});
  await assert.rejects(pipeline.initialize({}),/Face tracker failed/);
  assert.equal(affectRequested,false);
});

test('stalled model requests time out and can be retried', async () => {
  const filename=path.resolve(__dirname,'../src/lib/ml/affectScoring.ts');
  const actualRequire=createRequire(filename);
  const code=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  let triggerTimeout;
  let fetches=0;
  const context={AbortController,
    setTimeout:callback=>{triggerTimeout=callback;return 1;},clearTimeout:()=>{},console:{warn:()=>{}},
    fetch:(_url,options)=>{
      fetches++;
      if(fetches>1)return Promise.resolve({ok:false});
      return new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('Aborted')),{once:true}));
    }};
  const fixtureModule={exports:{}};
  const run=vm.runInNewContext(`(function(require,module,exports){${code}\n})`,context);
  run(name=>name==='@tensorflow/tfjs'?{}:actualRequire(name),fixtureModule,fixtureModule.exports);
  const pending=fixtureModule.exports.loadAffectModel();
  triggerTimeout();
  assert.equal(await pending,false);
  assert.equal(await fixtureModule.exports.loadAffectModel(),false);
  assert.equal(fetches,2);
});


function monitoringFixture() {
  let now = 10000;
  let brightness = 120;
  const landmarks = [{x:0.2,y:0.2,z:0},{x:0.8,y:0.8,z:0}];
  const pipeline = pipelineWith(async()=>({}),async()=>true, {
    './faceMesh': {detectFrame:()=>({faceLandmarks:[landmarks]}),getLandmarks:()=>landmarks},
    './eyeState': {EyeStateTracker:class {setBaseline(){} process(){return {sEye:1,eyesClosedDuration:0};}},getAverageEAR:()=>0.3},
    './headPose': {computeGazeScore:()=>({sGaze:1})},
    './yawnDetection': {YawnTracker:class {setBaseline(){} process(){return 1;}},computeMAR:()=>0.1},
    './affectScoring': {inferAffect:async()=>({engagement:0.7,boredom:0.2,confusion:0.3})},
  }, {Date:{now:()=>now},performance:{now:()=>now},document:{hidden:false}});
  pipeline.video={readyState:4,srcObject:{getVideoTracks:()=>[{readyState:'live',enabled:true}]},videoWidth:640,videoHeight:480};
  pipeline.state='running';
  pipeline.affectAvailable=true;
  pipeline.canvas={getContext:()=>({drawImage(){},getImageData:()=>({data:new Uint8ClampedArray(1024).fill(brightness)})})};
  const readings=[];
  pipeline.onReading(reading=>readings.push(reading));
  return {pipeline,readings,advance:ms=>{now+=ms;},dark:value=>{brightness=value?0:120;}};
}

test('valid faces remain scorable at two FPS instead of oscillating with frame-rate rejection', async()=>{
  const f=monitoringFixture();
  for(let i=0;i<20;i++){await f.pipeline.processFrame();f.advance(500);}
  assert.equal(f.readings.length,20);
  assert.ok(f.readings.every(r=>r.qualityFlag==='normal' && r.attentionIndex!==null && Math.abs(r.boredom-0.2)<1e-9));
});

test('brief bad images do not clear smoothing; sustained poor images still withdraw scores',async()=>{
  const f=monitoringFixture();
  await f.pipeline.processFrame();
  f.dark(true);f.advance(100);await f.pipeline.processFrame();
  assert.equal(f.readings.length,1);
  assert.equal(f.pipeline.affectWindow.length,1);
  f.dark(false);f.advance(500);await f.pipeline.processFrame();
  assert.equal(f.readings.at(-1).qualityFlag,'normal');
  f.dark(true);f.advance(100);await f.pipeline.processFrame();
  f.advance(1100);await f.pipeline.processFrame();
  assert.equal(f.readings.at(-1).attentionIndex,null);
  assert.equal(f.readings.at(-1).qualityFlag,'low_confidence');
});

test('a stopped pipeline never publishes a prediction that completes late',async()=>{
  const f=monitoringFixture();
  // Pause during the asynchronous prediction readback.
  const pending=f.pipeline.processFrame();
  f.pipeline.state='paused';
  await pending;
  assert.equal(f.readings.length,0);
});
