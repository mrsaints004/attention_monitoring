/* eslint-disable @typescript-eslint/no-require-imports -- Standalone verified model publisher. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const run = path.join(root, 'training/runs/sample-pilot-001');
const prepared = path.join(root, 'training/prepared/sample-pilot-002');
const output = path.join(root, 'frontend/public/models/daisee-pilot');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
execFileSync(process.execPath, [path.join(__dirname, 'verify_sample_pilot.cjs'), prepared, run], {stdio: 'inherit'});
const report = JSON.parse(fs.readFileSync(path.join(run, 'pilot_report.json')));
const replay = JSON.parse(fs.readFileSync(path.join(run, 'reload_verification.json')));
if (report.status !== 'sample_pilot_completed' || replay.status !== 'passed' || replay.clips !== 12) throw Error('Pilot evidence incomplete');
const model = fs.readFileSync(path.join(run, 'model.json')), weights = fs.readFileSync(path.join(run, 'weights.bin'));
if (hash(weights) !== report.weights_sha256) throw Error('Pilot checkpoint changed');
fs.mkdirSync(output, {recursive: true});
fs.writeFileSync(path.join(output, 'model.json'), model);
fs.writeFileSync(path.join(output, 'weights.bin'), weights);
fs.writeFileSync(path.join(output, 'metadata.json'), JSON.stringify({
 schema_version: 1, task: 'daisee-engagement-pilot', dataset: report.dataset,
 status: report.status, input: {shape: [32,32,3], region: 'full_frame', color_order: 'RGB', normalization: 'divide_by_255', live_resize: 'bilinear'},
 labels: ['very_low','low','high','very_high'], sampling_fps: 2,
 model_sha256: hash(model), weights_sha256: hash(weights),
 training: {clips: report.splits.Train.clips, epochs: report.epochs, selected_epoch: report.selected_epoch},
 validation: {clips: report.splits.Validation.clips, accuracy: report.splits.Validation.accuracy},
 test: {clips: report.splits.Test.clips, accuracy: report.splits.Test.accuracy, macro_f1: report.splits.Test.macro_f1},
 replay: {status: replay.status, absolute_tolerance: replay.absolute_tolerance, maximum_probability_difference: replay.maximum_probability_difference},
 scope: 'Trained 12-clip engagement-only pilot; auxiliary experiment; not part of the Attention Index',
 limitations: ['No boredom or confusion outputs','Four test clips; accuracy does not establish live generalisation',
 'Full-frame imagery can encode background and identity','Live bilinear resizing differs from FFmpeg training-frame scaling'],
}, null, 2) + '\n');
console.log('Verified DAiSEE engagement pilot published:', output);
