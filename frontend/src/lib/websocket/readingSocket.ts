import type { AttentionReading } from "../ml/pipeline";
import { studentCredential } from "../credentials";
const BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
export class ReadingSocket {
  private ws: WebSocket | null = null;
  private buffer: AttentionReading[] = [];
  private timer: ReturnType<typeof setTimeout> | null = null;
  private interval: ReturnType<typeof setInterval> | null = null;
  private disposed = false;
  private retries = 0;
  private lastSample = 0;
  private lastFlag = "";
  constructor(private sessionId: string, private studentId: string, private onStatus?: (status: string) => void) {}
  connect() {
    if (this.disposed || (this.ws && this.ws.readyState < WebSocket.CLOSING)) return;
    const credential = studentCredential(this.sessionId);
    if (!credential) { this.onStatus?.("Session access denied. Rejoin the session."); return; }
    const ws = new WebSocket(`${BASE}/ws/student/${this.sessionId}/${this.studentId}`, ["attention", credential]);
    this.ws = ws;
    ws.onopen = () => {
      this.retries = 0; this.onStatus?.("Connected");
      this.flush();
      this.interval = setInterval(() => this.flush(), 500);
    };
    ws.onclose = (event) => {
      if (this.interval) clearInterval(this.interval);
      this.onStatus?.(event.code === 1008 ? "Session access denied. Rejoin the session." : event.code === 1000 ? "Session ended" : "Reconnecting…");
      if (!this.disposed && event.code !== 1008 && event.code !== 1000) this.timer = setTimeout(() => this.connect(), Math.min(1000 * 2 ** this.retries++, 15000));
    };
    ws.onerror = () => ws.close();
  }
  private flush() {
    this.buffer = this.buffer.filter(r => Date.now() - r.timestamp < 30000);
    if (!this.buffer.length || this.ws?.readyState !== WebSocket.OPEN) return;
    const batch = this.buffer.slice(0, 100).map(r => ({ s_eye: r.sEye, s_gaze: r.sGaze, s_yawn: r.sYawn, s_affect: r.sAffect, inference_mode: r.affectAvailable ? "four_cue" : "geometric", attention_index: r.attentionIndex, quality_flag: r.qualityFlag, timestamp: new Date(r.timestamp).toISOString() }));
    this.ws.send(JSON.stringify(batch));
    this.buffer.splice(0, batch.length);
  }
  addReading(reading: AttentionReading) {
    // Analyse locally at 10 FPS; transmit at 1 Hz, with immediate state changes.
    if (reading.timestamp - this.lastSample < 1000 && reading.qualityFlag === this.lastFlag) return;
    this.lastSample = reading.timestamp; this.lastFlag = reading.qualityFlag;
    this.buffer.push(reading); this.buffer = this.buffer.slice(-30);
    if (reading.qualityFlag !== "normal") this.flush();
  }
  disconnect() {
    this.disposed = true;
    if (this.timer) clearTimeout(this.timer);
    if (this.interval) clearInterval(this.interval);
    this.ws?.close(); this.ws = null; this.buffer = [];
  }
}
