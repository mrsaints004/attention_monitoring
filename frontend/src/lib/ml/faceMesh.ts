import {
  FaceLandmarker,
  FilesetResolver,
  FaceLandmarkerResult,
} from "@mediapipe/tasks-vision";

let landmarker: FaceLandmarker | null = null;
let initPromise: Promise<FaceLandmarker> | null = null;

export type Results = FaceLandmarkerResult;

async function createLandmarker(): Promise<FaceLandmarker> {
  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm"
  );
  const options = {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
      delegate: "GPU" as const,
    },
    runningMode: "VIDEO" as const,
    numFaces: 2,
    minFaceDetectionConfidence: 0.8,
    minFacePresenceConfidence: 0.8,
    minTrackingConfidence: 0.8,
    outputFaceBlendshapes: false,
    outputFacialTransformationMatrixes: false,
  };
  try { return await FaceLandmarker.createFromOptions(vision, options); }
  catch { return FaceLandmarker.createFromOptions(vision, { ...options, baseOptions: { ...options.baseOptions, delegate: "CPU" } }); }
}

export async function initFaceMesh(): Promise<FaceLandmarker> {
  if (landmarker) return landmarker;
  if (!initPromise) {
    initPromise = createLandmarker();
  }
  try { landmarker = await initPromise; return landmarker; }
  catch (error) { initPromise = null; throw error; }
}

export function detectFrame(
  video: HTMLVideoElement,
  timestampMs: number
): FaceLandmarkerResult | null {
  if (!landmarker) return null;
  try {
    return landmarker.detectForVideo(video, timestampMs);
  } catch {
    return null;
  }
}

// Convert FaceLandmarkerResult landmarks to the format expected by our modules
export interface NormalizedLandmark {
  x: number;
  y: number;
  z: number;
}

export function getLandmarks(result: FaceLandmarkerResult): NormalizedLandmark[] | null {
  if (!result.faceLandmarks || result.faceLandmarks.length === 0) return null;
  return result.faceLandmarks[0] as NormalizedLandmark[];
}
