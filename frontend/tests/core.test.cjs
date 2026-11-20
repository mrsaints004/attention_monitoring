/* eslint-disable @typescript-eslint/no-require-imports -- Node CommonJS test harness transpiles the project TypeScript modules. */
const fs = require('node:fs');
const ts = require('typescript');
// Exercise the actual TypeScript modules without a second test framework.
require.extensions['.ts'] = (module, path) => module._compile(ts.transpileModule(fs.readFileSync(path, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, path);
const test = require('node:test');
const assert = require('node:assert/strict');
const { CueFusion } = require('../src/lib/ml/cueFusion.ts');
const { EyeStateTracker } = require('../src/lib/ml/eyeState.ts');
const { YawnTracker } = require('../src/lib/ml/yawnDetection.ts');
const { historyTimeline } = require('../src/lib/history.ts');

test('missing affect is excluded and remaining weights are normalised', () => {
  const fusion = new CueFusion();
  assert.equal(fusion.compute({ sEye: 1, sGaze: 1, sYawn: 1, sAffect: 0 }, 0, false).attentionIndex, 100);
});
test('sustained eye closure caps the displayed smoothed score immediately', () => {
  const fusion = new CueFusion(); const cues = { sEye: 1, sGaze: 1, sYawn: 1, sAffect: 1 };
  fusion.compute(cues, 0);
  assert.ok(fusion.compute(cues, 4).attentionIndex <= 15);
});
test('a short blink never reduces the eye score', () => {
  const eye = new EyeStateTracker(); eye.setBaseline(0.3);
  eye.process(0.3, 1000); eye.process(0.1, 1100); eye.process(0.1, 1200);
  assert.equal(eye.process(0.3, 1300).sEye, 1);
});
test('time weighted eye state detects sustained closure at variable frame rate', () => {
  const eye = new EyeStateTracker(); eye.setBaseline(0.3);
  for (let t = 1000; t <= 4000; t += 200) eye.process(0.1, t);
  const score = eye.process(0.1, 4200);
  assert.equal(score.sEye, 0); assert.ok(score.eyesClosedDuration > 3);
});
test('a yawn requires sustained mouth opening and recovers over ten seconds', () => {
  const yawn = new YawnTracker(); yawn.setBaseline(0.1);
  assert.equal(yawn.process(0.8, 1000), 1);
  assert.equal(yawn.process(0.8, 2500), 0);
  assert.equal(yawn.process(0.1, 2600), 0);
  assert.equal(yawn.process(0.1, 7600), 0.5);
});
test('class timeline gives each student equal weight and excludes missing evidence', () => {
  const row = (student_id, attention_index, quality_flag = 'normal') => ({ student_id, attention_index, quality_flag, timestamp: '2026-10-17T12:00:00' });
  const series = historyTimeline([row('a', 100), row('a', 100), row('b', 0), row('c', null, 'monitoring_paused')], true);
  assert.equal(series[0].attention, 50);
  assert.equal(historyTimeline([row('a', null, 'away')], true)[0].attention, null);
});

test('perspective pose fit recovers known yaw and pitch', () => {
  const { estimateYawPitch } = require('../src/lib/ml/headPose.ts');
  const yaw = 20 * Math.PI / 180, pitch = -10 * Math.PI / 180;
  const landmarks = Array.from({ length: 478 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
  for (const [index, [x,y,z]] of [[1,[0,0,0]],[152,[0,.63,-.12]],[33,[-.43,-.32,-.26]],[263,[.43,-.32,-.26]],[61,[-.28,.28,-.24]],[291,[.28,.28,-.24]]]) {
    const y1 = Math.cos(pitch)*y-Math.sin(pitch)*z, z1 = Math.sin(pitch)*y+Math.cos(pitch)*z;
    const x2 = Math.cos(yaw)*x+Math.sin(yaw)*z1, z2 = -Math.sin(yaw)*x+Math.cos(yaw)*z1;
    landmarks[index] = { x: .5 + x2/(z2+4), y: .5 + (4/3)*y1/(z2+4), z: 0 };
  }
  const result = estimateYawPitch(landmarks);
  assert.ok(Math.abs(result.yaw-20)<1, JSON.stringify(result));
  assert.ok(Math.abs(result.pitch+10)<1, JSON.stringify(result));
});

test('reading transport samples at one Hz, bounds offline buffer, and reports quality changes immediately', () => {
  const { ReadingSocket } = require('../src/lib/websocket/readingSocket.ts');
  const socket = new ReadingSocket('session', 'student');
  const timestamp = Date.now() - 60000;
  const base = { sEye: 1, sGaze: 1, sYawn: 1, sAffect: 0.5, attentionIndex: 90, qualityFlag: 'normal' };
  for (let i = 0; i < 600; i++) socket.addReading({ ...base, timestamp: timestamp + i * 100 });
  assert.equal(socket.buffer.length, 30);
  assert.equal(socket.buffer[1].timestamp - socket.buffer[0].timestamp, 1000);
  socket.addReading({ ...base, timestamp: timestamp + 59950, attentionIndex: null, qualityFlag: 'monitoring_paused' });
  assert.equal(socket.buffer.at(-1).qualityFlag, 'monitoring_paused');
  assert.equal(socket.buffer.length, 30);
  socket.disconnect();
  assert.equal(socket.buffer.length, 0);
});

test('affect metadata accepts native RGB input and rejects unfinished checkpoints', () => {
  const { parseAffectModelSpec } = require('../src/lib/ml/affectModelSpec.ts');
  const source = JSON.parse(fs.readFileSync(require('node:path').join(__dirname, '../../training/model_spec.json')));
  assert.throws(() => parseAffectModelSpec(source));
  const metadata = { ...source, training: { status: 'fine_tuned', dataset: 'DAiSEE', model_sha256: 'a'.repeat(64) }, parity: { status: 'passed', absolute_tolerance: .0001 } };
  assert.deepEqual(parseAffectModelSpec(metadata).input.shape, [224,224,3]);
  assert.throws(() => parseAffectModelSpec({ ...metadata, labels: ['high','low','very_low','very_high'] }));
  assert.throws(() => parseAffectModelSpec({ ...metadata, parity: { status: 'failed', absolute_tolerance: 0 } }));
});

test('four-level affect scoring rejects emotion outputs and malformed probabilities', () => {
  const { expectedAffectLevel } = require('../src/lib/ml/affectModelSpec.ts');
  assert.equal(expectedAffectLevel([1,0,0,0]), 0);
  assert.equal(expectedAffectLevel([0,0,0,1]), 1);
  assert.equal(expectedAffectLevel([.25,.25,.25,.25]), .5);
  for (const values of [[0,0,0,0], [0,0,1,0,0,0,0], [NaN,0,0,1], [.5,.5,.5,.5], [-1,0,0,2]]) assert.throws(() => expectedAffectLevel(values));
});

test('RGB preprocessing preserves channel order, subtracts source means and releases tensors', async () => {
  const tf = require('@tensorflow/tfjs');
  const { prepareAffectInput } = require('../src/lib/ml/affectScoring.ts');
  await tf.setBackend('cpu'); await tf.ready();
  const spec = JSON.parse(fs.readFileSync(require('node:path').join(__dirname, '../../training/model_spec.json')));
  spec.input.shape = [2,2,3];
  const pixels = tf.tensor3d([110,120,130,110,120,130,110,120,130,110,120,130], [2,2,3]);
  const before = tf.memory().numTensors;
  for (let iteration=0; iteration<5; iteration++) {
    const result = prepareAffectInput(pixels, [0,0,1,1], spec);
    assert.deepEqual(result.shape, [1,2,2,3]);
    const values = await result.data();
    for (let channel=0; channel<3; channel++) assert.ok(Math.abs(values[channel] - ([110,120,130][channel]-spec.input.mean[channel])) < .0001);
    result.dispose();
  }
  assert.equal(tf.memory().numTensors, before);
  pixels.dispose();
});

test('standalone export verifier loads weight shards and rejects prediction mismatches', async () => {
  const os = require('node:os');
  const path = require('node:path');
  const { spawnSync } = require('node:child_process');
  const tf = require('@tensorflow/tfjs');
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'affect-parity-test-'));
  const input = tf.input({shape:[2,2,3]});
  const flat = tf.layers.flatten().apply(input);
  const heads = ['engagement', 'boredom', 'confusion'].map(name => tf.layers.dense({units:4, activation:'softmax', name, kernelInitializer:'zeros', biasInitializer:'zeros'}));
  const model = tf.model({inputs:input, outputs:heads.map(head => head.apply(flat))});
  const kernel = new Float32Array(12*4); kernel[3] = .05;
  const weights = tf.tensor2d(kernel,[12,4]), bias = tf.zeros([4]);
  heads.forEach(head => head.setWeights([weights,bias]));
  weights.dispose(); bias.dispose();
  try {
    await model.save(tf.io.withSaveHandler(async artifacts => {
      fs.writeFileSync(path.join(folder,'model.json'),JSON.stringify({modelTopology:artifacts.modelTopology, weightsManifest:[{paths:['weights.bin'], weights:artifacts.weightSpecs}]}));
      fs.writeFileSync(path.join(folder,'weights.bin'),Buffer.from(artifacts.weightData));
      return {modelArtifactsInfo:{dateSaved:new Date(),modelTopologyType:'JSON'}};
    }));
    const pixels = Array.from({length:4},()=>[110,120,130]).flat();
    const mean = [103.939,116.779,123.68];
    const exponent = Math.exp((110-mean[0])*.05), other = 1/(3+exponent);
    const expected = [other,other,other,exponent/(3+exponent)];
    const probes = {input:{shape:[2,2,3],mean}, cases:[{pixels, expected:[expected,expected,expected]}]};
    const file = path.join(folder,'probes.json'); fs.writeFileSync(file,JSON.stringify(probes));
    const script = path.resolve(__dirname,'../../training/verify_export.cjs');
    let result = spawnSync(process.execPath,[script,folder,file],{encoding:'utf8'});
    assert.equal(result.status,0,result.stderr);
    probes.cases[0].expected[0] = [1,0,0,0]; fs.writeFileSync(file,JSON.stringify(probes));
    result = spawnSync(process.execPath,[script,folder,file],{encoding:'utf8'});
    assert.notEqual(result.status,0);
    assert.match(result.stderr,/Conversion mismatch/);
  } finally { model.dispose(); fs.rmSync(folder,{recursive:true,force:true}); }
});


test('deployed DAiSEE pilot predicts with bounded probabilities and no tensor leak', async () => {
  const tf = require('@tensorflow/tfjs');
  const { loadPilotModel } = require('../src/lib/ml/pilotScoring.ts');
  const path = require('node:path');
  const originalFetch = global.fetch;
  const base = path.resolve(__dirname, '../public');
  global.fetch = async url => new Response(fs.readFileSync(path.join(base, String(url))));
  let pilot;
  try {
    await tf.setBackend('cpu');
    pilot = await loadPilotModel();
    const report = JSON.parse(fs.readFileSync(path.join(base, 'models/daisee-pilot/metadata.json')));
    assert.equal(report.test.accuracy, 0.25);
    const before = tf.memory().numTensors;
    const pixels = tf.fill([48, 64, 3], 127, 'int32');
    const prediction = await pilot.predictPixels(pixels);
    assert.equal(prediction.probabilities.length, 4);
    assert.ok(prediction.engagement >= 0 && prediction.engagement <= 1);
    pixels.dispose();
    assert.equal(tf.memory().numTensors, before);
    pilot.dispose(); pilot.dispose();
  } finally { global.fetch = originalFetch; pilot?.dispose(); }
});

test('deployed pilot refuses altered trained weights', async () => {
  const { loadPilotModel } = require('../src/lib/ml/pilotScoring.ts');
  const path = require('node:path');
  const originalFetch = global.fetch;
  global.fetch = async url => {
    const bytes = Buffer.from(fs.readFileSync(path.resolve(__dirname, '../public', '.' + String(url))));
    if (String(url).endsWith('weights.bin')) bytes[0] ^= 1;
    return new Response(bytes);
  };
  try { await assert.rejects(loadPilotModel(), /integrity check failed/); }
  finally { global.fetch = originalFetch; }
});

test('full DAiSEE release matches measured evidence and predicts all three heads', async () => {
  const tf = require('@tensorflow/tfjs');
  const path = require('node:path');
  const folder = path.resolve(__dirname, '../public/models/fer');
  const metadata = JSON.parse(fs.readFileSync(path.join(folder, 'metadata.json')));
  const report = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../src/lib/data/daiseeFullReport.json')));
  assert.equal(metadata.training.status, 'fine_tuned');
  assert.equal(metadata.training.model_sha256, report.model_sha256);
  assert.equal(report.test.total_clips, 1784);
  assert.equal(report.test.scorable_clips, 1780);
  const document = JSON.parse(fs.readFileSync(path.join(folder, 'model.json')));
  const specs = document.weightsManifest.flatMap(group => group.weights);
  const bytes = Uint8Array.from(Buffer.concat(document.weightsManifest.flatMap(group => group.paths.map(file => fs.readFileSync(path.join(folder, file))))));
  const model = await tf.loadLayersModel(tf.io.fromMemory({modelTopology:document.modelTopology,weightSpecs:specs,weightData:bytes.buffer}));
  assert.deepEqual(model.outputNames, ['engagement','boredom','confusion']);
  const before = tf.memory().numTensors;
  const input = tf.zeros([1,224,224,3]);
  const predictions = model.predict(input);
  try {
    for (const prediction of predictions) {
      const values = Array.from(await prediction.data());
      assert.equal(values.length,4);
      assert.ok(values.every(value => Number.isFinite(value) && value >= 0 && value <= 1));
      assert.ok(Math.abs(values.reduce((sum,value)=>sum+value,0)-1)<0.0001);
    }
  } finally { input.dispose();predictions.forEach(t=>t.dispose()); }
  assert.equal(tf.memory().numTensors,before);
  model.dispose();
});
