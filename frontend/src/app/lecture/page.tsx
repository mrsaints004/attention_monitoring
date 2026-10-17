"use client";
import { useEffect, useRef, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useCamera } from "@/hooks/useCamera";
import { useAttentionPipeline } from "@/hooks/useAttentionPipeline";
import { SelfView } from "@/components/SelfView";
import { MonitoringIndicator } from "@/components/MonitoringIndicator";
import { LectureMedia } from "@/components/LectureMedia";
import { ReadingSocket } from "@/lib/websocket/readingSocket";
import { ConfirmModal } from "@/components/Modal";
import { api } from "@/lib/api";

function LecturePageContent() {
  const params = useSearchParams(); const router = useRouter();
  const sessionId = params.get("session") || "";
  const studentId = params.get("student") || "";
  const { stream, mediaStream, startCamera, stopCamera } = useCamera();
  const { state, latestReading, initialize, startMonitoring, pause, resume, stop, onReading, setCalibrationData, calibrationProgress } = useAttentionPipeline();
  const socket = useRef<ReadingSocket | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [course, setCourse] = useState("Lecture"); const [error, setError] = useState("");
  const [status, setStatus] = useState("Connecting…");
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [withdrawBusy, setWithdrawBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    if (!sessionId || !studentId || sessionStorage.getItem(`consent:${sessionId}`) !== "v1" || localStorage.getItem(`student:${sessionId}`) !== studentId) {
      router.replace(`/join?session=${encodeURIComponent(sessionId)}`); return;
    }
    const setup = async () => {
      try {
        const session = await api.getSession(sessionId);
        if (session.ended_at) throw new Error("This session has ended.");
        if (cancelled) return; setCourse(session.course_name);
        await startCamera();
        if (cancelled) { stopCamera(); return; }
        if (!stream.current || !video.current) throw new Error("Camera unavailable. Allow camera access and retry.");
        video.current.srcObject = stream.current; await video.current.play();
        await initialize(video.current);
        if (cancelled) return;
        const stored = sessionStorage.getItem(`calibration:${sessionId}`);
        if (!stored) { router.replace(`/join?session=${sessionId}`); return; }
        setCalibrationData(JSON.parse(stored));
        const ws = new ReadingSocket(sessionId, studentId, status => { setStatus(status); if (status === "Session ended") { stop(); stopCamera(); } }); socket.current = ws;
        ws.connect(); startMonitoring(); setError("");
      } catch (err) { if (!cancelled) setError(err instanceof Error ? err.message : "Monitoring could not start. Retry or rejoin the session."); }
    };
    void setup();
    return () => { cancelled = true; socket.current?.disconnect(); socket.current = null; stop(); stopCamera(); };
  }, [sessionId, studentId, router, startCamera, stopCamera, stream, initialize, setCalibrationData, startMonitoring, stop, attempt]);
  useEffect(() => onReading(r => socket.current?.addReading(r)), [onReading]);
  const leave = () => { pause(); socket.current?.disconnect(); stop(); stopCamera(); sessionStorage.removeItem(`calibration:${sessionId}`); router.push("/"); };
  const withdraw = async () => {
    setWithdrawBusy(true); pause();
    try {
      await api.withdrawStudent(sessionId, studentId);
      localStorage.removeItem(`student:${sessionId}`); localStorage.removeItem(`device:${sessionId}`);
      sessionStorage.removeItem(`consent:${sessionId}`); leave();
    } catch (err) { setError(err instanceof Error ? err.message : "Withdrawal failed. Retry when connected."); }
    finally { setWithdrawBusy(false); setWithdrawOpen(false); }
  };
  return <main id="main-content" className="flex-1 min-h-screen bg-gray-100">
    <ConfirmModal open={withdrawOpen} title="Withdraw consent" message="Stop monitoring and delete your stored scores and alias from this session? Previously downloaded exports cannot be recalled." confirmLabel="Withdraw and delete my data" variant="danger" confirmDisabled={withdrawBusy} onConfirm={withdraw} onCancel={() => setWithdrawOpen(false)} />
    <header className="flex flex-wrap gap-3 items-center justify-between bg-white p-4 shadow-sm">
      <h1 className="text-lg font-semibold">{course}</h1>
      <div className="flex flex-wrap gap-3 items-center">
        {latestReading && <MonitoringIndicator attentionIndex={latestReading.attentionIndex} qualityFlag={latestReading.qualityFlag} />}
        <button disabled={state !== "running" && state !== "paused"} onClick={() => state === "paused" ? resume() : pause()} className="rounded-lg border px-4 py-2">{state === "paused" ? "Resume" : "Pause"} monitoring</button>
        <button disabled={withdrawBusy} onClick={() => setWithdrawOpen(true)} className="rounded-lg border px-4 py-2">Withdraw consent</button>
        <button onClick={leave} className="rounded-lg bg-red-100 px-4 py-2 text-red-800">Leave lecture</button>
      </div>
    </header>
    <div className="max-w-6xl mx-auto p-4 space-y-4">
      {error && <div role="alert" className="rounded-lg bg-red-50 p-4 text-red-800">{error} <button className="underline px-3" onClick={() => setAttempt(x => x + 1)}>Retry</button><button className="underline px-3" onClick={() => router.push(`/join?session=${sessionId}`)}>Rejoin and calibrate</button></div>}
      <p role="status" className="text-sm text-gray-700">Monitoring connection: {status}</p>
      {status === "Session ended" && <p role="status">The instructor has ended this session. You can leave the lecture.</p>}
      <LectureMedia sessionId={sessionId} identity={studentId} />
      {state === "calibrating" && <p role="status" className="rounded bg-blue-50 p-4">Recalibrating after your return. Look at the screen with your eyes open. {Math.round(calibrationProgress * 100)}%</p>}
      {latestReading && !latestReading.affectAvailable && <p className="text-sm text-gray-700">Experimental three-cue mode: eye state, gaze and yawning. Facial-affect model unavailable. Scores are estimates for teaching support, not assessment.</p>}
      {latestReading?.qualityFlag === "low_confidence" && <p role="status" className="text-amber-800">Improve the lighting and keep only your face in view. No attention score is reported while the image is unreliable.</p>}
      <div className="w-48"><SelfView stream={mediaStream} /></div>
    </div>
    <video ref={video} autoPlay playsInline muted className="sr-only" />
  </main>;
}
export default function LecturePage() { return <Suspense fallback={<p className="p-6">Loading lecture…</p>}><LecturePageContent /></Suspense>; }
