import * as tf from "@tensorflow/tfjs";
import { NormalizedLandmark } from "./faceMesh";

// Optional DAiSEE model contract: [1,48,48,1] input, four engagement
// probabilities ordered Very Low, Low, High, Very High.
let model: tf.LayersModel | null = null;
let modelPromise: Promise<boolean> | null = null;
let modelFailed = false;

export async function loadAffectModel(): Promise<boolean> {
  if (model) return true;
  if (modelFailed) return false;
  if (!modelPromise) modelPromise = (async () => {
    try {
      const loaded = await tf.loadLayersModel("/models/fer/model.json");
      const output = loaded.outputs[0].shape;
      if (loaded.inputs.length !== 1 || loaded.outputs.length !== 1 || output[output.length - 1] !== 4 || loaded.inputs[0].shape.slice(1).join(",") !== "48,48,1") {
        loaded.dispose();
        throw new Error("Engagement model requires 48×48 grayscale input and four DAiSEE probabilities");
      }
      model = loaded;
      return true;
    } catch {
      console.warn("DAiSEE affect model unavailable; using explicitly labelled geometric-cue mode");
      modelFailed = true;
      return false;
    }
  })();
  return modelPromise;
}

export async function inferExpression(
  video: HTMLVideoElement,
  landmarks: NormalizedLandmark[],
  videoWidth: number,
  videoHeight: number
): Promise<number> {
  if (model) {
    return inferWithModel(video, landmarks, videoWidth, videoHeight);
  }
  throw new Error("Facial-affect model is unavailable");
}

async function inferWithModel(
  video: HTMLVideoElement,
  landmarks: NormalizedLandmark[],
  videoWidth: number,
  videoHeight: number
): Promise<number> {
  // Crop face region from video
  const bbox = getFaceBoundingBox(landmarks, videoWidth, videoHeight);

  const score = tf.tidy(() => {
    let tensor = tf.browser.fromPixels(video);
    // Crop face
    tensor = tf.image.cropAndResize(
      tensor.expandDims(0).toFloat() as tf.Tensor4D,
      [[bbox.y1 / videoHeight, bbox.x1 / videoWidth, bbox.y2 / videoHeight, bbox.x2 / videoWidth]],
      [0],
      [48, 48]
    ).squeeze() as tf.Tensor3D;

    // Convert to grayscale
    const gray = tensor.mean(2).expandDims(-1).expandDims(0).div(255);
    const prediction = model!.predict(gray) as tf.Tensor;
    const scores = prediction.dataSync();

    if (scores.length !== 4 || Array.from(scores).some(p => !Number.isFinite(p) || p < 0)) throw new Error("Invalid model probabilities");
    const total = Array.from(scores).reduce((a, b) => a + b, 0);
    if (total <= 0) throw new Error("Invalid model probabilities");
    return (scores[1] + 2 * scores[2] + 3 * scores[3]) / (3 * total);
  });

  return Math.max(0, Math.min(1, score));
}

function getFaceBoundingBox(
  landmarks: NormalizedLandmark[],
  width: number,
  height: number
): { x1: number; y1: number; x2: number; y2: number } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const lm of landmarks) {
    const x = lm.x * width;
    const y = lm.y * height;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  // Add margin
  const margin = 0.1;
  const w = maxX - minX;
  const h = maxY - minY;
  return {
    x1: Math.max(0, minX - w * margin),
    y1: Math.max(0, minY - h * margin),
    x2: Math.min(width, maxX + w * margin),
    y2: Math.min(height, maxY + h * margin),
  };
}
