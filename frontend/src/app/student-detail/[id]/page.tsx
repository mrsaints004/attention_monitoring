"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { historyTimeline, utcDate } from "@/lib/history";
import { api, ReadingData } from "@/lib/api";
import { DashboardSocket, DashboardData, DashboardStudentData } from "@/lib/websocket/dashboardSocket";
import { CueBreakdown } from "@/components/CueBreakdown";
import { AttentionTimeline } from "@/components/AttentionTimeline";
import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import Link from "next/link";

function StudentDetailPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const studentId = params.id as string;
  const sessionId = searchParams.get("session") || "";
  const [student, setStudent] = useState<DashboardStudentData | null>(null);
  const [error, setError] = useState("");
  const [readings, setReadings] = useState<ReadingData[]>([]);

  const handleDashboardUpdate = useCallback((data: DashboardData) => {
    const s = data.students.find((s) => s.student_id === studentId);
    if (s) setStudent(s);
  }, [studentId]);

  useEffect(() => {
    if (!sessionId) return;
    const socket = new DashboardSocket(sessionId, handleDashboardUpdate);
    socket.connect();
    return () => socket.disconnect();
  }, [sessionId, handleDashboardUpdate]);

  // Fetch historical readings
  useEffect(() => {
    if (!sessionId || !studentId) return;
    const fetchReadings = () => {
      api.getReadings(sessionId, studentId, 300).then(async rows => {
        setReadings(rows);
        const session = await api.getSession(sessionId);
        const info = session.students.find(s => s.student_id === studentId);
        const latest = rows[0];
        const fresh = !session.ended_at && latest && Date.now() - utcDate(latest.timestamp).getTime() < 5000;
        if (info && latest) setStudent(previous => previous || { ...info, ...latest, attention_index: fresh ? latest.attention_index : null, quality_flag: fresh ? latest.quality_flag : "monitoring_paused" });
        else if (info) setStudent({ ...info, attention_index: null, quality_flag: "monitoring_paused", s_eye: 0, s_gaze: 0, s_yawn: 0, s_affect: 0 });
        else setError("Student not found in this session.");
      }).catch(err => setError(err.message));
    };
    fetchReadings();
    const interval = setInterval(fetchReadings, 5000);
    return () => clearInterval(interval);
  }, [sessionId, studentId]);

  const timelineData = historyTimeline(readings);

  const loading = !student;

  return (
    <main id="main-content" role="main" className="flex-1 flex flex-col bg-gray-50">
      <header className="bg-white shadow-sm px-6 py-4 flex items-center gap-4">
        <Link
          href={`/console?session=${sessionId}`}
          aria-label="Back to console"
          className="text-blue-600 hover:text-blue-800"
        >
          &larr; Back
        </Link>
        <div>
          {loading ? (
            <>
              <Skeleton className="h-7 w-40 mb-1" />
              <Skeleton className="h-4 w-24" />
            </>
          ) : (
            <>
              <h1 className="text-xl font-bold text-gray-900">
                {student.display_name}
              </h1>
              <p className="text-sm text-gray-500">Student Detail</p>
            </>
          )}
        </div>
      </header>

      {error && <p role="alert" className="p-6 text-red-800">{error}</p>}
      <div className="flex-1 p-6">
        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <SkeletonCard />
            <div className="lg:col-span-2">
              <SkeletonCard />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Live attention */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Current Monitoring Status
              </h2>
              <div className="text-center mb-6" aria-live="polite">
                <span className="text-6xl font-bold text-gray-900">
                  {student.attention_index === null ? "—" : Math.round(student.attention_index)}
                </span>
                <span className="text-2xl text-gray-400">/100</span>
              </div>
              <p className="mb-4 text-sm capitalize">{student.quality_flag.replaceAll("_", " ")}</p>
              <CueBreakdown
                affectAvailable={student.inference_mode === "four_cue"}
                sEye={student.s_eye}
                sGaze={student.s_gaze}
                sYawn={student.s_yawn}
                sAffect={student.s_affect}
              />
            </div>

            {/* Timeline */}
            <div className="lg:col-span-2 bg-white rounded-xl shadow p-6">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Recent Attention Readings
              </h2>
              <AttentionTimeline data={timelineData} showCues />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function StudentDetailPage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center">Loading...</div>}>
      <StudentDetailPageContent />
    </Suspense>
  );
}
