export function instructorCredential(sessionId: string) {
  return typeof window === "undefined" ? "" : localStorage.getItem(`instructor:${sessionId}`) || "";
}
export function studentCredential(sessionId: string) {
  return typeof window === "undefined" ? "" : localStorage.getItem(`device:${sessionId}`) || "";
}
export function authHeaders(sessionId: string, instructor = true) {
  return { Authorization: `Bearer ${instructor ? instructorCredential(sessionId) : studentCredential(sessionId)}` };
}
