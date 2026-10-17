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
