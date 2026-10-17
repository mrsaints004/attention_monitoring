import { NormalizedLandmark } from "./faceMesh";
import { euclideanDistance2D, Point3D } from "../utils/mathUtils";
import { EAR_CLOSED_RATIO, BLINK_MAX_DURATION_MS, EYE_WINDOW_MS } from "./constants";

// MediaPipe Face Mesh eye landmark indices
const LEFT_EYE = { top: 159, bottom: 145, outerCorner: 33, innerCorner: 133, topOuter: 158, bottomOuter: 153 };
const RIGHT_EYE = { top: 386, bottom: 374, outerCorner: 362, innerCorner: 263, topOuter: 385, bottomOuter: 380 };

function landmarkToPoint(lm: NormalizedLandmark): Point3D {
  return { x: lm.x, y: lm.y, z: lm.z || 0 };
}

function computeEAR(landmarks: NormalizedLandmark[], eye: typeof LEFT_EYE): number {
  const p1 = landmarkToPoint(landmarks[eye.topOuter]);
  const p2 = landmarkToPoint(landmarks[eye.bottomOuter]);
  const p3 = landmarkToPoint(landmarks[eye.top]);
  const p4 = landmarkToPoint(landmarks[eye.bottom]);
  const p5 = landmarkToPoint(landmarks[eye.outerCorner]);
  const p6 = landmarkToPoint(landmarks[eye.innerCorner]);

  const vertical1 = euclideanDistance2D(p1, p2);
  const vertical2 = euclideanDistance2D(p3, p4);
  const horizontal = euclideanDistance2D(p5, p6);

  if (horizontal === 0) return 0;
  return (vertical1 + vertical2) / (2.0 * horizontal);
}

export function getAverageEAR(landmarks: NormalizedLandmark[]): number {
  const leftEAR = computeEAR(landmarks, LEFT_EYE);
  const rightEAR = computeEAR(landmarks, RIGHT_EYE);
  return (leftEAR + rightEAR) / 2;
}

interface EyeEvent {
  timestamp: number;
  isOpen: boolean;
}

export class EyeStateTracker {
  private baselineEAR = 0;
  private events: EyeEvent[] = [];
  private closedSince: number | null = null;

  setBaseline(ear: number) {
    this.baselineEAR = ear;
  }

  getBaseline(): number {
    return this.baselineEAR;
  }

  process(ear: number, now: number): { sEye: number; eyesClosedDuration: number } {
    if (this.events.length && now - this.events[this.events.length - 1].timestamp > 500) {
      this.events = []; this.closedSince = null;
    }
    const isOpen = ear >= this.baselineEAR * EAR_CLOSED_RATIO;
    if (!isOpen && this.closedSince === null) this.closedSince = now;
    if (isOpen && this.closedSince !== null) {
      if (now - this.closedSince <= BLINK_MAX_DURATION_MS) {
        for (const event of this.events) if (event.timestamp >= this.closedSince) event.isOpen = true;
      }
      this.closedSince = null;
    }
    this.events.push({ timestamp: now, isOpen });
    const windowStart = now - EYE_WINDOW_MS;
    // Keep the sample immediately before the window boundary for interpolation.
    while (this.events.length > 1 && this.events[1].timestamp <= windowStart) this.events.shift();
    let openMs = 0, totalMs = 0;
    const pendingBlink = this.closedSince !== null && now - this.closedSince <= BLINK_MAX_DURATION_MS;
    for (let i = 0; i < this.events.length - 1; i++) {
      const event = this.events[i];
      const duration = this.events[i + 1].timestamp - Math.max(windowStart, event.timestamp);
      if (duration <= 0) continue;
      totalMs += duration;
      if (event.isOpen || (pendingBlink && event.timestamp >= this.closedSince!)) openMs += duration;
    }
    const sEye = totalMs > 0 ? openMs / totalMs : 1;
    const eyesClosedDuration = this.closedSince !== null ? (now - this.closedSince) / 1000 : 0;

    return { sEye, eyesClosedDuration };
  }
}
