import { NormalizedLandmark } from "./faceMesh";
import { getAverageEAR } from "./eyeState";
import { computeMAR } from "./yawnDetection";
import { computeGazeScore } from "./headPose";
import { mean, stddev } from "../utils/mathUtils";
import { CALIBRATION_FRAMES, CALIBRATION_TIMEOUT_MS } from "./constants";

export interface CalibrationData {
  baselineEAR: number;
  baselineMAR: number;
  baselineGaze: number;
  baselineYaw?: number;
  baselinePitch?: number;
  earStdDev: number;
  marStdDev: number;
}

export class Calibrator {
  private earSamples: number[] = [];
  private marSamples: number[] = [];
  private yawSamples: number[] = [];
  private pitchSamples: number[] = [];
  private gazeSamples: number[] = [];
  private startTime = 0;
  private _isComplete = false;

  start() {
    this.earSamples = [];
    this.marSamples = [];
    this.gazeSamples = [];
    this.yawSamples = []; this.pitchSamples = [];
    this.startTime = Date.now();
    this._isComplete = false;
  }

  addFrame(landmarks: NormalizedLandmark[], aspectRatio = 4 / 3): { progress: number; timedOut: boolean } {
    const ear = getAverageEAR(landmarks);
    const mar = computeMAR(landmarks);
    const { sGaze, yaw, pitch } = computeGazeScore(landmarks, 0, 0, aspectRatio);

    this.earSamples.push(ear);
    this.marSamples.push(mar);
    this.gazeSamples.push(sGaze);
    this.yawSamples.push(yaw); this.pitchSamples.push(pitch);

    const progress = Math.min(1, this.earSamples.length / CALIBRATION_FRAMES, (Date.now() - this.startTime) / 5000);
    const timedOut = Date.now() - this.startTime > CALIBRATION_TIMEOUT_MS;

    if (this.earSamples.length >= CALIBRATION_FRAMES && Date.now() - this.startTime >= 5000) {
      this._isComplete = true;
    }

    return { progress, timedOut };
  }

  isComplete(): boolean {
    return this._isComplete;
  }

  getResult(): CalibrationData | null {
    if (this.earSamples.length < CALIBRATION_FRAMES) return null;

    return {
      baselineEAR: mean(this.earSamples),
      baselineMAR: mean(this.marSamples),
      baselineGaze: mean(this.gazeSamples),
      baselineYaw: mean(this.yawSamples), baselinePitch: mean(this.pitchSamples),
      earStdDev: stddev(this.earSamples),
      marStdDev: stddev(this.marSamples),
    };
  }

  reset() {
    this.start();
  }
}
