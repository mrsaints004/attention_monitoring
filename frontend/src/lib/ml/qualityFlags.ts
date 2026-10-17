import { NormalizedLandmark } from "./faceMesh";
import { LOW_CONFIDENCE_THRESHOLD } from "./constants";

export type QualityFlag =
  | "normal"
  | "face_not_detected"
  | "away"
  | "low_confidence"
  | "tab_inactive"
  | "monitoring_paused";

export function determineQualityFlag(
  landmarks: NormalizedLandmark[] | null,
  detectionConfidence: number,
  isPaused: boolean,
  gazeDeviation?: number
): QualityFlag {
  if (isPaused) return "monitoring_paused";

  if (typeof document !== "undefined" && document.visibilityState === "hidden") {
    return "tab_inactive";
  }

  if (!landmarks || landmarks.length === 0) {
    return "face_not_detected";
  }

  if (detectionConfidence < LOW_CONFIDENCE_THRESHOLD) {
    return "low_confidence";
  }

  // If gaze deviation is extremely high, student is looking far away
  if (gazeDeviation !== undefined && gazeDeviation > 50) {
    return "away";
  }

  return "normal";
}
