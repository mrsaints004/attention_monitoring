import { authHeaders } from "./credentials";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === "string" ? err.detail : "Please check the entered details and try again.");
  }
  return res.json();
}

export interface SessionCreated {
  instructor_token: string;
  session_id: string;
  join_code: string;
}

export interface StudentInfo {
  student_id: string;
  display_name: string;
  joined_at: string;
}

export interface SessionInfo {
  session_id: string;
  join_code: string;
  course_name: string;
  instructor_name: string;
  started_at: string;
  ended_at: string | null;
  students: StudentInfo[];
}

export interface JoinResult {
  student_id: string;
  device_token: string;
  session_id: string;
}

export interface ReadingData {
  reading_id: string;
  student_id: string;
  timestamp: string;
  s_eye: number;
  s_gaze: number;
  s_yawn: number;
  s_affect: number;
  inference_mode?: "geometric" | "four_cue";
  attention_index: number | null;
  quality_flag: string;
}

export const api = {
  createSession(data: { instructor_name: string; instructor_email: string; course_name: string }) {
    return request<SessionCreated>("/api/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getSession(sessionId: string) {
    return request<SessionInfo>(`/api/sessions/${sessionId}`, { headers: authHeaders(sessionId) });
  },

  getSessionByCode(code: string) {
    return request<SessionInfo>(`/api/sessions/code/${code}`);
  },

  joinSession(sessionId: string, data: { display_name: string; device_token?: string }) {
    return request<JoinResult>(`/api/sessions/${sessionId}/join`, {
      method: "POST",
      body: JSON.stringify({ ...data, consent_version: "v1" }),
    });
  },

  withdrawStudent(sessionId: string, studentId: string) {
    return request(`/api/sessions/${sessionId}/students/${studentId}/withdraw`, { method: "POST", headers: authHeaders(sessionId, false) });
  },

  endSession(sessionId: string) {
    return request<{ status: string }>(`/api/sessions/${sessionId}/end`, {
      method: "POST", headers: authHeaders(sessionId),
    });
  },

  getReadings(sessionId: string, studentId?: string, limit = 500, offset = 0) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (studentId) params.set("student_id", studentId);
    return request<ReadingData[]>(`/api/sessions/${sessionId}/readings?${params}`, { headers: authHeaders(sessionId) });
  },

  async getAllReadings(sessionId: string) {
    const readings: ReadingData[] = [];
    for (let offset = 0; ; offset += 1000) {
      const page = await api.getReadings(sessionId, undefined, 1000, offset);
      readings.push(...page);
      if (page.length < 1000) return readings;
    }
  },

  async downloadExport(sessionId: string) {
    const response = await fetch(`${API_BASE}/api/sessions/${sessionId}/export`, { headers: authHeaders(sessionId) });
    if (!response.ok) throw new Error("Could not export this session. Check instructor access and try again.");
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `session_${sessionId}.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
