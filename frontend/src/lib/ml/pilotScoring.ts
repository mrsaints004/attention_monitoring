import * as tf from "@tensorflow/tfjs";
import { expectedAffectLevel } from "./affectModelSpec";

export interface PilotPrediction {
  engagement: number;
  predictedLevel: number;
  probabilities: number[];
}
export interface PilotMetadata {
  task: "daisee-engagement-pilot";
  status: "sample_pilot_completed";
  model_sha256: string;
  weights_sha256: string;
  test: { clips: number; accuracy: number };
}

async function verify(bytes: ArrayBuffer, expected: string) {
  if (!/^[a-f0-9]{64}$/.test(expected)) throw new Error("Missing pilot integrity record");
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const actual = Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
  if (actual !== expected) throw new Error("Pilot model integrity check failed");
}

export function preparePilotInput(pixels: tf.Tensor3D): tf.Tensor4D {
  return tf.tidy(() => tf.image.resizeBilinear(pixels, [32, 32]).div(255).expandDims(0) as tf.Tensor4D);
}

export class PilotModel {
  private disposed = false;
  constructor(private model: tf.LayersModel, readonly metadata: PilotMetadata) {}

  async predictPixels(pixels: tf.Tensor3D): Promise<PilotPrediction> {
    const output = tf.tidy(() => this.model.predict(preparePilotInput(pixels)) as tf.Tensor);
    try {
      const probabilities = Array.from(await output.data());
      const engagement = expectedAffectLevel(probabilities);
      return { engagement, predictedLevel: probabilities.indexOf(Math.max(...probabilities)), probabilities };
    } finally { output.dispose(); }
  }

  async predict(video: HTMLVideoElement): Promise<PilotPrediction> {
    const pixels = tf.browser.fromPixels(video);
    try { return await this.predictPixels(pixels); }
    finally { pixels.dispose(); }
  }

  dispose() { if (!this.disposed) { this.disposed = true; this.model.dispose(); } }
}

export async function loadPilotModel(): Promise<PilotModel> {
  const base = "/models/daisee-pilot";
  const metadataResponse = await fetch(`${base}/metadata.json`, {signal: AbortSignal.timeout(15000)});
  if (!metadataResponse.ok) throw new Error("Trained pilot model is unavailable");
  const metadata = await metadataResponse.json();
  if (metadata.task !== "daisee-engagement-pilot" || metadata.status !== "sample_pilot_completed" ||
      metadata.dataset !== "DAiSEE" || metadata.replay?.status !== "passed" ||
      JSON.stringify(metadata.input?.shape) !== "[32,32,3]" || metadata.input?.region !== "full_frame" ||
      metadata.input?.normalization !== "divide_by_255" || metadata.input?.color_order !== "RGB" ||
      JSON.stringify(metadata.labels) !== '["very_low","low","high","very_high"]' ||
      metadata.test?.clips !== 4 || !Number.isFinite(metadata.test?.accuracy)) {
    throw new Error("Incompatible pilot metadata");
  }
  const [modelResponse, weightsResponse] = await Promise.all([fetch(`${base}/model.json`, {signal: AbortSignal.timeout(15000)}), fetch(`${base}/weights.bin`, {signal: AbortSignal.timeout(15000)})]);
  if (!modelResponse.ok || !weightsResponse.ok) throw new Error("Pilot model files could not be loaded");
  const [modelBytes, weights] = await Promise.all([modelResponse.arrayBuffer(), weightsResponse.arrayBuffer()]);
  await Promise.all([verify(modelBytes, metadata.model_sha256), verify(weights, metadata.weights_sha256)]);
  const definition = JSON.parse(new TextDecoder().decode(modelBytes));
  if (definition.weightsManifest?.length !== 1 || JSON.stringify(definition.weightsManifest[0].paths) !== '["weights.bin"]') {
    throw new Error("Unsupported pilot weight manifest");
  }
  await tf.ready();
  const model = await tf.loadLayersModel(tf.io.fromMemory({modelTopology: definition.modelTopology,
    weightSpecs: definition.weightsManifest[0].weights, weightData: weights}));
  try {
    if (model.inputs.length !== 1 || JSON.stringify(model.inputs[0].shape.slice(1)) !== "[32,32,3]" ||
        model.outputs.length !== 1 || model.outputs[0].shape[1] !== 4) throw new Error("Pilot model shape mismatch");
    return new PilotModel(model, metadata);
  } catch (error) { model.dispose(); throw error; }
}
