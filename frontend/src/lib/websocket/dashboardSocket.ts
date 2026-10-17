import { instructorCredential } from "../credentials";
const API_WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface DashboardStudentData {
  student_id: string;
  display_name: string;
  inference_mode?: "geometric" | "four_cue";
  attention_index: number | null;
  quality_flag: string;
  s_eye: number;
  s_gaze: number;
  s_yawn: number;
  s_affect: number;
}

export interface DashboardAlertData {
  alert_id: string;
  student_id: string;
  reading_id: string;
  alert_type: string;
  triggered_at: string;
}

export interface DashboardData {
  type: string;
  class_average: number | null;
  student_count: number;
  students: DashboardStudentData[];
  recent_alerts: DashboardAlertData[];
}

export class DashboardSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private onUpdate: (data: DashboardData) => void;
  private onStatusChange?: (connected: boolean) => void;
  private disposed = false;

  constructor(
    sessionId: string,
    onUpdate: (data: DashboardData) => void,
    onStatusChange?: (connected: boolean) => void
  ) {
    this.sessionId = sessionId;
    this.onUpdate = onUpdate;
    this.onStatusChange = onStatusChange;
  }

  connect() {
    if (this.disposed) return;

    const credential = instructorCredential(this.sessionId);
    if (!credential) { this.onStatusChange?.(false); return; }
    this.ws = new WebSocket(`${API_WS_BASE}/ws/instructor/${this.sessionId}`, ["attention", credential]);

    this.ws.onopen = () => {
      this.onStatusChange?.(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const data: DashboardData = JSON.parse(event.data);
        if (data.type === "dashboard_update") {
          this.onUpdate(data);
        }
      } catch {
        // Ignore parse errors
      }
    };

    this.ws.onclose = (event) => {
      this.onStatusChange?.(false);
      // Auto-reconnect after 2s unless disposed
      if (!this.disposed && event.code !== 1008) {
        setTimeout(() => this.connect(), 2000);
      }
    };
  }

  disconnect() {
    this.disposed = true;
    this.ws?.close();
    this.ws = null;
  }
}
