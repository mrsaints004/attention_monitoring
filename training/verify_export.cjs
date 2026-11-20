/* eslint-disable @typescript-eslint/no-require-imports -- Standalone Node conversion check. */
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const frontendRequire = createRequire(path.resolve(__dirname, '../frontend/package.json'));
const tf = frontendRequire('@tensorflow/tfjs');
async function main() {
  const [folder, probePath] = process.argv.slice(2);
  if (!folder || !probePath) throw new Error('Usage: node training/verify_export.cjs MODEL_FOLDER PROBES_JSON');
  await tf.setBackend('cpu');
  const document = JSON.parse(fs.readFileSync(path.join(folder, 'model.json')));
  const specs = [], chunks = [];
  for (const group of document.weightsManifest) {
    specs.push(...group.weights);
    for (const filename of group.paths) {
      const asset = path.resolve(folder, filename);
      if (!asset.startsWith(path.resolve(folder) + path.sep)) throw new Error('Unsafe weight path');
      chunks.push(fs.readFileSync(asset));
    }
  }
  const bytes = Uint8Array.from(Buffer.concat(chunks));
  const model = await tf.loadLayersModel(tf.io.fromMemory({modelTopology: document.modelTopology, weightSpecs: specs, weightData: bytes.buffer}));
  const probes = JSON.parse(fs.readFileSync(probePath));
  let largestError = 0;
  for (const probe of probes.cases) {
    const input = tf.tidy(() => tf.tensor3d(probe.pixels, probes.input.shape).sub(tf.tensor1d(probes.input.mean)).expandDims(0));
    const outputs = model.predict(input);
    if (!Array.isArray(outputs) || outputs.length !== 3) throw new Error('Expected engagement, boredom and confusion heads');
    try {
      for (let head = 0; head < outputs.length; head++) {
        const actual = await outputs[head].data();
        if (actual.length !== 4) throw new Error('Expected four probabilities per head');
        for (let index = 0; index < 4; index++) {
          const error = Math.abs(actual[index] - probe.expected[head][index]);
          if (!Number.isFinite(error) || error > 0.0001) throw new Error(`Conversion mismatch: head ${head}, class ${index}, error ${error}`);
          largestError = Math.max(largestError, error);
        }
      }
    } finally { input.dispose(); outputs.forEach(output => output.dispose()); }
  }
  model.dispose();
  process.stdout.write(`Python/TensorFlow.js parity passed. Largest error: ${largestError}\n`);
}
main().catch(error => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
