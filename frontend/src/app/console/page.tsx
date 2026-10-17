"use client";

import { useEffect, useState, useRef, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api, SessionInfo } from "@/lib/api";
import { DashboardSocket, DashboardData, DashboardAlertData } from "@/lib/websocket/dashboardSocket";
import { instructorCredential } from "@/lib/credentials";
import { LectureMedia } from "@/components/LectureMedia";
import { StudentGrid } from "@/components/StudentGrid";
import { ClassAverageGauge } from "@/components/ClassAverageGauge";
import { AlertFeed } from "@/components/AlertFeed";
import { ConfirmModal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Copy, Check, WifiOff } from "lucide-react";

function ConsolePageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const sessionId = searchParams.get("session") || "";
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [allAlerts, setAllAlerts] = useState<DashboardAlertData[]>([]);
  const [elapsed, setElapsed] = useState("00:00:00");
  const [showEndModal, setShowEndModal] = useState(false);
  const [copied, setCopied] = useState(false);
  const [wsConnected, setWsConnected] = useState(true);
  const socketRef = useRef<DashboardSocket | null>(null);

  const [error, setError] = useState("");
  useEffect(() => {
    const loadSession = async () => {
      if (!instructorCredential(sessionId)) throw new Error("Instructor access is unavailable in this browser. Open the browser that created the session, or create a new session.");
      return api.getSession(sessionId);
    };
    loadSession().then(setSession).catch(err => setError(err.message));
  }, [sessionId]);

  const handleDashboardUpdate = useCallback((data: DashboardData) => {
    setDashboard(data);
    if (data.recent_alerts.length > 0) {
      setAllAlerts(data.recent_alerts);
    }
  }, []);

  const handleWsStatus = useCallback((connected: boolean) => {
    setWsConnected(connected);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const socket = new DashboardSocket(sessionId, handleDashboardUpdate, handleWsStatus);
    socket.connect();
    socketRef.current = socket;
    return () => socket.disconnect();
  }, [sessionId, handleDashboardUpdate, handleWsStatus]);

  // Session timer
  useEffect(() => {
    if (!session?.started_at) return;
    const start = new Date(session.started_at).getTime();
    const interval = setInterval(() => {
      const diff = Math.floor((Date.now() - start) / 1000);
      const h = String(Math.floor(diff / 3600)).padStart(2, "0");
      const m = String(Math.floor((diff % 3600) / 60)).padStart(2, "0");
      const s = String(diff % 60).padStart(2, "0");
      setElapsed(`${h}:${m}:${s}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [session?.started_at]);

  const handleCopyJoinCode = async () => {
    if (!session?.join_code) return;
    try {
      await navigator.clipboard.writeText(session.join_code);
      setCopied(true);
      toast.success("Join code copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy join code");
    }
  };

  const handleEndSession = async () => {
    setShowEndModal(false);
    try { await api.endSession(sessionId); router.push(`/history/${sessionId}`); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not end session. Try again."); }
  };

  return (
    <main id="main-content" role="main" className="flex-1 flex flex-col bg-gray-50">
      <ConfirmModal
        open={showEndModal}
        title="End Session"
        message="End this session? Students will be disconnected."
        variant="danger"
        confirmLabel="End Session"
        onConfirm={handleEndSession}
        onCancel={() => setShowEndModal(false)}
      />

      {/* Header */}
      <header className="bg-white shadow-sm px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            {session?.course_name || "Loading..."}
          </h1>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>Join code:</span>
            <button
              onClick={handleCopyJoinCode}
              className="inline-flex items-center gap-1.5 font-mono font-bold text-blue-600 hover:text-blue-800 transition-colors px-2 py-0.5 rounded hover:bg-blue-50"
              aria-label={`Copy join code ${session?.join_code || ""}`}
            >
              {session?.join_code}
              {copied ? (
                <Check className="w-4 h-4 text-green-500" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {!wsConnected && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 border border-amber-200 text-amber-700 rounded-full text-sm font-medium">
              <WifiOff className="w-4 h-4" />
              Reconnecting...
            </div>
          )}
          <span className="font-mono text-lg text-gray-600">{elapsed}</span>
          <button
            onClick={() => setShowEndModal(true)}
            className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors"
          >
            End Session
          </button>
        </div>
      </header>

      {error && <p role="alert" className="p-4 text-red-800">{error}</p>}
      <p className="px-6 pt-4 text-sm text-gray-700">Experimental estimates for teaching support. Unavailable readings are excluded from averages. Scores must not be used for grading or discipline.</p>
      <div className="px-6 pt-6"><LectureMedia sessionId={sessionId} identity={`instructor-${sessionId}`} instructor /></div>
      {/* Dashboard content */}
      <div className="flex-1 p-6" aria-live="polite">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left: Main dashboard area */}
          <div className="lg:col-span-3 space-y-6">
            <StudentGrid
              students={dashboard?.students || []}
              sessionId={sessionId}
            />
          </div>

          {/* Right: Stats sidebar */}
          <div className="space-y-6">
            <ClassAverageGauge
              average={dashboard?.class_average ?? null}
              studentCount={dashboard?.student_count || 0}
            />
            <AlertFeed
              alerts={allAlerts}
              students={dashboard?.students || []}
            />
          </div>
        </div>
      </div>
    </main>
  );
}

export default function ConsolePage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center">Loading...</div>}>
      <ConsolePageContent />
    </Suspense>
  );
}
