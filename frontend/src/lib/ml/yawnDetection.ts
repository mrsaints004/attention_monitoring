import { NormalizedLandmark } from "./faceMesh";
import { euclideanDistance2D, Point3D } from "../utils/mathUtils";
import { MAR_YAWN_OFFSET, YAWN_MIN_DURATION_MS, YAWN_RECOVERY_MS } from "./constants";

// Mouth landmark indices
const UPPER_LIP_TOP = 13;
const LOWER_LIP_BOTTOM = 14;
const LEFT_MOUTH_CORNER = 61;
const RIGHT_MOUTH_CORNER = 291;
const UPPER_LIP_OUTER = 12;
const LOWER_LIP_OUTER = 15;

function landmarkToPoint(lm: NormalizedLandmark): Point3D {
  return { x: lm.x, y: lm.y, z: lm.z || 0 };
}

export function computeMAR(landmarks: NormalizedLandmark[]): number {
  const upperTop = landmarkToPoint(landmarks[UPPER_LIP_TOP]);
  const lowerBottom = landmarkToPoint(landmarks[LOWER_LIP_BOTTOM]);
  const upperOuter = landmarkToPoint(landmarks[UPPER_LIP_OUTER]);
  const lowerOuter = landmarkToPoint(landmarks[LOWER_LIP_OUTER]);
  const leftCorner = landmarkToPoint(landmarks[LEFT_MOUTH_CORNER]);
  const rightCorner = landmarkToPoint(landmarks[RIGHT_MOUTH_CORNER]);

  const vertical1 = euclideanDistance2D(upperTop, lowerBottom);
  const vertical2 = euclideanDistance2D(upperOuter, lowerOuter);
  const horizontal = euclideanDistance2D(leftCorner, rightCorner);

  if (horizontal === 0) return 0;
  return (vertical1 + vertical2) / (2.0 * horizontal);
}

export class YawnTracker {
  private baselineMAR = 0;
  private yawnStart: number | null = null;
  private lastYawnEnd: number | null = null;

  setBaseline(mar: number) {
    this.baselineMAR = mar;
  }

  getBaseline(): number {
    return this.baselineMAR;
  }

  process(mar: number, now: number): number {
    const threshold = this.baselineMAR + MAR_YAWN_OFFSET;
    const isYawning = mar > threshold;

    if (isYawning) {
      if (this.yawnStart === null) {
        this.yawnStart = now;
      }
    } else {
      if (this.yawnStart !== null) {
        const duration = now - this.yawnStart;
        if (duration >= YAWN_MIN_DURATION_MS) {
          this.lastYawnEnd = now;
        }
        this.yawnStart = null;
      }
    }

    // Currently mid-yawn (long enough to count)
    if (this.yawnStart !== null && (now - this.yawnStart) >= YAWN_MIN_DURATION_MS) {
      return 0;
    }

    // Recovery period after yawn
    if (this.lastYawnEnd !== null) {
      const elapsed = now - this.lastYawnEnd;
      if (elapsed < YAWN_RECOVERY_MS) {
        return elapsed / YAWN_RECOVERY_MS;
      }
    }

    return 1.0;
  }
}
