/* eslint-disable @typescript-eslint/no-require-imports -- Test the real pipeline with controlled network/model dependencies. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const ts = require('typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,filename);
function pipelineWith(initFaceMesh, loadAffectModel) {
  const filename = path.resolve(__dirname,'../src/lib/ml/pipeline.ts');
  const code = ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  const actualRequire = createRequire(filename);
  const fixtureModule = {exports:{}};
  const requireDependency = name => name === './faceMesh' ? {initFaceMesh} : name === './affectScoring' ? {loadAffectModel} : actualRequire(name);
  const run = vm.runInNewContext(`(function(require,module,exports){${code}\n})`);
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
