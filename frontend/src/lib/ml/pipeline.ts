import { initFaceMesh, detectFrame, getLandmarks } from "./faceMesh";
import { EyeStateTracker, getAverageEAR } from "./eyeState";
import { computeGazeScore } from "./headPose";
import { YawnTracker, computeMAR } from "./yawnDetection";
import { inferExpression, loadAffectModel } from "./affectScoring";
import { CueFusion } from "./cueFusion";
import { Calibrator, CalibrationData } from "./calibration";
import { QualityFlag } from "./qualityFlags";
import { FrameThrottle } from "../utils/frameThrottle";

export interface AttentionReading {
  sEye: number; sGaze: number; sYawn: number; sAffect: number;
  attentionIndex: number | null; qualityFlag: QualityFlag; timestamp: number;
  affectAvailable?: boolean;
}
export type PipelineState = "idle" | "calibrating" | "running" | "paused";
export type PipelineListener = (reading: AttentionReading) => void;
export class AttentionPipeline {
  private video: HTMLVideoElement | null = null;
  private state: PipelineState = "idle";
  private throttle = new FrameThrottle(10);
  private eye = new EyeStateTracker();
  private yawn = new YawnTracker();
  private fusion = new CueFusion();
  private calibrator = new Calibrator();
  private calibration: CalibrationData | null = null;
  private missingSince = 0;
  private recalibrateOnReturn = false;
  private automaticCalibration = false;
  private affectAvailable = false;
  private lastAffect = 0.5;
  private lastAffectTime = 0;
  private busy = false;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private lastFrameTime = 0;
  private frameTimes: number[] = [];
  private monitoringSince = 0;
  private canvas: HTMLCanvasElement | null = null;
  private listeners: PipelineListener[] = [];
  private calibrationListeners: ((progress: number) => void)[] = [];
  private stateListeners: ((state: PipelineState) => void)[] = [];
  onReading(cb: PipelineListener) { this.listeners.push(cb); return () => { this.listeners = this.listeners.filter(x => x !== cb); }; }
  onCalibrationProgress(cb: (progress: number) => void) { this.calibrationListeners.push(cb); return () => { this.calibrationListeners = this.calibrationListeners.filter(x => x !== cb); }; }
  onStateChange(cb: (state: PipelineState) => void) { this.stateListeners.push(cb); return () => { this.stateListeners = this.stateListeners.filter(x => x !== cb); }; }
  getState() { return this.state; }
  private setState(state: PipelineState) { this.state = state; this.stateListeners.forEach(cb => cb(state)); }
  async initialize(video: HTMLVideoElement) {
    this.video = video;
    await initFaceMesh();
    this.affectAvailable = await loadAffectModel();
  }
  private startLoop() {
    this.throttle.start(() => { void this.processFrame(); });
    if (!this.heartbeat) this.heartbeat = setInterval(() => {
      if (this.state === "paused") this.emitUnavailable("monitoring_paused");
      else if (this.state === "running" && document.hidden) this.emitUnavailable("tab_inactive");
      else if (this.state === "running" && Date.now() - this.lastFrameTime > 2000) this.emitUnavailable("low_confidence");
    }, 1000);
  }
  startCalibration() { this.automaticCalibration = false; this.calibrator.start(); this.setState("calibrating"); this.startLoop(); }
  setCalibrationData(data: CalibrationData) {
    if (!Number.isFinite(data.baselineEAR) || data.baselineEAR <= 0 || !Number.isFinite(data.baselineMAR) || data.baselineMAR < 0) throw new Error("Invalid calibration. Please rejoin and calibrate.");
    this.calibration = data; this.eye.setBaseline(data.baselineEAR); this.yawn.setBaseline(data.baselineMAR);
  }
  getCalibrationData() { return this.calibration; }
  startMonitoring() { this.monitoringSince = Date.now(); this.frameTimes = []; if (!this.calibration) throw new Error("Calibration is required. Please rejoin the session."); this.lastFrameTime = Date.now(); this.setState("running"); this.startLoop(); }
  pause() { this.setState("paused"); this.emitUnavailable("monitoring_paused"); }
  resume() { this.missingSince = 0; this.monitoringSince = Date.now(); this.frameTimes = []; this.fusion.reset(); this.eye = new EyeStateTracker(); this.yawn = new YawnTracker(); if (this.calibration) this.setCalibrationData(this.calibration); this.setState("running"); }
  stop() { this.throttle.stop(); if (this.heartbeat) clearInterval(this.heartbeat); this.heartbeat = null; this.fusion.reset(); this.setState("idle"); }
  private emitUnavailable(flag: QualityFlag) { this.eye = new EyeStateTracker(); this.yawn = new YawnTracker(); this.fusion.reset(); if (this.calibration) this.setCalibrationData(this.calibration); this.listeners.forEach(cb => cb({ sEye: 0, sGaze: 0, sYawn: 0, sAffect: 0, attentionIndex: null, qualityFlag: flag, timestamp: Date.now(), affectAvailable: this.affectAvailable })); }
  private async processFrame() {
    if (this.busy || !this.video || this.state === "idle" || this.state === "paused") return;
    this.busy = true;
    try {
      const now = Date.now(); this.lastFrameTime = now;
      this.frameTimes.push(now); this.frameTimes = this.frameTimes.filter(t => now - t <= 2000);
      if (this.video.readyState < 2 || !this.video.srcObject || !(this.video.srcObject as MediaStream).getVideoTracks().some(t => t.readyState === "live" && t.enabled)) { this.emitUnavailable("monitoring_paused"); return; }
      if (document.hidden) { this.emitUnavailable("tab_inactive"); return; }
      const result = detectFrame(this.video, performance.now());
      const landmarks = result ? getLandmarks(result) : null;
      if (!landmarks) {
        if (!this.missingSince) this.missingSince = now;
        if (now - this.missingSince >= 30000) this.recalibrateOnReturn = true;
        if (now - this.missingSince >= 5000) this.emitUnavailable(this.recalibrateOnReturn ? "away" : "face_not_detected");
        return;
      }
      this.missingSince = 0;
      if (this.recalibrateOnReturn) {
        this.recalibrateOnReturn = false; this.automaticCalibration = true;
        this.eye = new EyeStateTracker(); this.yawn = new YawnTracker(); this.fusion.reset();
        this.calibrator.start(); this.setState("calibrating");
      }
      if ((result?.faceLandmarks.length ?? 0) > 1) { this.emitUnavailable("low_confidence"); return; }
      this.canvas ??= document.createElement("canvas");
      this.canvas.width = this.canvas.height = 16;
      const ctx = this.canvas.getContext("2d", { willReadFrequently: true });
      if (ctx) {
        const xs = landmarks.map(p => p.x), ys = landmarks.map(p => p.y);
        const x = Math.max(0, Math.min(...xs)), y = Math.max(0, Math.min(...ys));
        const w = Math.min(1, Math.max(...xs)) - x, h = Math.min(1, Math.max(...ys)) - y;
        if (w <= 0 || h <= 0) { this.emitUnavailable("low_confidence"); return; }
        ctx.drawImage(this.video, x * this.video.videoWidth, y * this.video.videoHeight, w * this.video.videoWidth, h * this.video.videoHeight, 0, 0, 16, 16);
        const pixels = ctx.getImageData(0, 0, 16, 16).data;
        let brightness = 0;
        for (let i = 0; i < pixels.length; i += 4) brightness += (pixels[i] + pixels[i+1] + pixels[i+2]) / 3;
        if (brightness / 256 < 35) { this.emitUnavailable("low_confidence"); return; }
      }
      if (this.state === "calibrating") {
        const { progress, timedOut } = this.calibrator.addFrame(landmarks, this.video.videoWidth / this.video.videoHeight);
        this.calibrationListeners.forEach(cb => cb(progress));
        if (this.calibrator.isComplete()) {
          const data = this.calibrator.getResult();
          if (data) this.setCalibrationData(data);
          if (this.automaticCalibration) { this.automaticCalibration = false; this.setState("running"); }
          else { this.throttle.stop(); this.setState("idle"); }
        } else if (timedOut) this.calibrator.reset();
        return;
      }
      if (now - this.monitoringSince > 2000 && this.frameTimes.length < 10) { this.emitUnavailable("low_confidence"); return; }
      const { sEye, eyesClosedDuration } = this.eye.process(getAverageEAR(landmarks), now);
      const { sGaze } = computeGazeScore(landmarks, this.calibration?.baselineYaw ?? 0, this.calibration?.baselinePitch ?? 0, this.video.videoWidth / this.video.videoHeight);
      const sYawn = this.yawn.process(computeMAR(landmarks), now);
      if (this.affectAvailable && now - this.lastAffectTime >= 333) {
        try { this.lastAffect = await inferExpression(this.video, landmarks, this.video.videoWidth, this.video.videoHeight); }
        catch { this.affectAvailable = false; }
        this.lastAffectTime = now;
      }
      const { attentionIndex } = this.fusion.compute({ sEye, sGaze, sYawn, sAffect: this.lastAffect }, eyesClosedDuration, this.affectAvailable);
      this.listeners.forEach(cb => cb({ sEye, sGaze, sYawn, sAffect: this.lastAffect, attentionIndex, qualityFlag: "normal", timestamp: now, affectAvailable: this.affectAvailable }));
    } catch { this.emitUnavailable("low_confidence"); }
    finally { this.busy = false; }
  }
}
