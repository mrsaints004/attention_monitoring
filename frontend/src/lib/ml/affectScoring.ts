import * as tf from "@tensorflow/tfjs";
import type { NormalizedLandmark } from "./faceMesh";
import { AffectModelSpec, expectedAffectLevel, parseAffectModelSpec } from "./affectModelSpec";

export interface AffectPrediction { engagement: number; boredom: number; confusion: number; }
let model: tf.LayersModel | null = null;
let spec: AffectModelSpec | null = null;
let modelPromise: Promise<boolean> | null = null;

export async function loadAffectModel(): Promise<boolean> {
  if (model) return true;
  if (!modelPromise) modelPromise = (async () => {
    let loaded: tf.LayersModel | null = null;
    try {
      const response = await fetch("/models/fer/metadata.json");
      if (!response.ok) return false;
      const metadata = parseAffectModelSpec(await response.json());
      loaded = await tf.loadLayersModel("/models/fer/model.json");
      if (loaded.inputs.length !== 1 || loaded.outputs.length !== 3 ||
          JSON.stringify(loaded.inputs[0].shape.slice(1)) !== JSON.stringify(metadata.input.shape) ||
          loaded.outputNames.join(",") !== "engagement,boredom,confusion" ||
          loaded.outputs.some(output => output.shape.length !== 2 || output.shape[1] !== 4)) {
        throw new Error("Checkpoint does not match its declared MobileNet interface");
      }
      // Exercise supported operators before treating the model as available.
      const warmup = tf.zeros([1, ...metadata.input.shape]);
      let predictions: tf.Tensor[] = [];
      try {
        predictions = loaded.predict(warmup) as tf.Tensor[];
        for (const prediction of predictions) expectedAffectLevel(await prediction.data());
      } finally { warmup.dispose(); predictions.forEach(prediction => prediction.dispose()); }
      model = loaded;
      spec = metadata;
      return true;
    } catch {
      loaded?.dispose();
      console.warn("Compatible fine-tuned affect model unavailable; using geometric cues");
      return false;
    }
  })();
  return modelPromise;
}

export function prepareAffectInput(pixels: tf.Tensor3D, box: [number, number, number, number], metadata: AffectModelSpec): tf.Tensor4D {
  return tf.tidy(() => {
    const [height, width] = metadata.input.shape;
    const crop = tf.image.cropAndResize(pixels.toFloat().expandDims(0) as tf.Tensor4D, [box], [0], [height, width]);
    // Preparation stores lossless uint8 crops; apply the same truncation here.
    return crop.floor().sub(tf.tensor1d(metadata.input.mean)) as tf.Tensor4D;
  });
}

export async function inferAffect(video: HTMLVideoElement, landmarks: NormalizedLandmark[]): Promise<AffectPrediction> {
  if (!model || !spec) throw new Error("Facial-affect model is unavailable");
  const xs = landmarks.map(point => point.x), ys = landmarks.map(point => point.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const dx = (maxX - minX) * spec.crop_margin, dy = (maxY - minY) * spec.crop_margin;
  const box: [number, number, number, number] = [Math.max(0, minY - dy), Math.max(0, minX - dx), Math.min(1, maxY + dy), Math.min(1, maxX + dx)];
  if (box.some(value => !Number.isFinite(value)) || box[2] <= box[0] || box[3] <= box[1]) throw new Error("Invalid face region");
  const predictions = tf.tidy(() => {
    const input = prepareAffectInput(tf.browser.fromPixels(video), box, spec!);
    return model!.predict(input) as tf.Tensor[];
  });
  try {
    const [engagement, boredom, confusion] = await Promise.all(predictions.map(async prediction => expectedAffectLevel(await prediction.data())));
    return { engagement, boredom, confusion };
  } finally { predictions.forEach(prediction => prediction.dispose()); }
}
