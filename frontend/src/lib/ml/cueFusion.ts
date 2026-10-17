import { W_EYE, W_GAZE, W_YAWN, W_AFFECT, EMA_ALPHA, EYES_CLOSED_CAP_SECONDS, EYES_CLOSED_CAP_INDEX } from "./constants";
import { clamp } from "../utils/mathUtils";

export interface CueScores {
  sEye: number;
  sGaze: number;
  sYawn: number;
  sAffect: number;
}

export interface FusionResult {
  attentionIndex: number;
  cueScores: CueScores;
}

export class CueFusion {
  private prevIndex: number | null = null;

  compute(scores: CueScores, eyesClosedDuration: number, affectAvailable = true): FusionResult {
    let raw = 100 * (
      W_EYE * scores.sEye +
      W_GAZE * scores.sGaze +
      W_YAWN * scores.sYawn +
      (affectAvailable ? W_AFFECT * scores.sAffect : 0)
    );

    if (!affectAvailable) raw /= (W_EYE + W_GAZE + W_YAWN);

    // Safety: eyes closed > 3s → cap index
    if (eyesClosedDuration > EYES_CLOSED_CAP_SECONDS) {
      raw = Math.min(raw, EYES_CLOSED_CAP_INDEX);
    }

    raw = clamp(raw, 0, 100);

    // EMA smoothing
    let smoothed: number;
    if (this.prevIndex === null) {
      smoothed = raw;
    } else {
      smoothed = EMA_ALPHA * raw + (1 - EMA_ALPHA) * this.prevIndex;
    }
    if (eyesClosedDuration > EYES_CLOSED_CAP_SECONDS) smoothed = Math.min(smoothed, EYES_CLOSED_CAP_INDEX);
    this.prevIndex = smoothed;

    return {
      attentionIndex: Math.round(smoothed * 10) / 10,
      cueScores: scores,
    };
  }

  reset() {
    this.prevIndex = null;
  }
}
