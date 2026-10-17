"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { historyTimeline, utcDate } from "@/lib/history";
import { api, SessionInfo, ReadingData } from "@/lib/api";
import { AttentionTimeline } from "@/components/AttentionTimeline";
import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import { BarChart3 } from "lucide-react";
import Link from "next/link";

export default function HistoryPage() {
  const params = useParams();
  const sessionId = params.id as string;
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [readings, setReadings] = useState<ReadingData[] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [selectedStudent, setSelectedStudent] = useState<string>("all");

  useEffect(() => {
    if (!sessionId) return;
    Promise.all([api.getSession(sessionId), api.getAllReadings(sessionId)]).then(([session, readings]) => { setSession(session); setReadings(readings); setError(""); }).catch(err => setError(err.message));
  }, [sessionId, attempt]);

  const loading = !session || readings === null;

  const filteredReadings = readings
    ? selectedStudent === "all"
      ? readings
      : readings.filter((r) => r.student_id === selectedStudent)
    : [];

  const timelineData = historyTimeline(filteredReadings, selectedStudent === "all");
  const scores = timelineData.flatMap(r => r.attention === null ? [] : [r.attention]);
  const avgAttention = scores.length ? scores.reduce((a,b) => a+b,0) / scores.length : null;
  const minAttention = scores.length ? scores.reduce((a,b) => Math.min(a,b), Infinity) : null;
  const maxAttention = scores.length ? scores.reduce((a,b) => Math.max(a,b), -Infinity) : null;
  if (error) return <main id="main-content" className="p-6"><p role="alert">{error}</p><button onClick={() => setAttempt(x => x+1)} className="underline p-3">Retry</button><Link href="/">Home</Link></main>;

  if (loading) {
    return (
      <main id="main-content" role="main" className="flex-1 flex flex-col bg-gray-50">
        <header className="bg-white shadow-sm px-6 py-4">
          <Skeleton className="h-7 w-64 mb-2" />
          <Skeleton className="h-4 w-40" />
        </header>
        <div className="flex-1 p-6 space-y-6">
          <SkeletonCard />
          <div className="grid grid-cols-3 gap-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <SkeletonCard />
        </div>
      </main>
    );
  }

  return (
    <main id="main-content" role="main" className="flex-1 flex flex-col bg-gray-50">
      <header className="bg-white shadow-sm px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">
            Session History: {session?.course_name || "Loading..."}
          </h1>
          <p className="text-sm text-gray-500">
            {session?.started_at && utcDate(session.started_at).toLocaleDateString()}
            {session?.ended_at && ` — ${utcDate(session.ended_at).toLocaleTimeString()}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="px-4 py-2 text-gray-500 hover:text-gray-700"
          >
            Home
          </Link>
          <button
            onClick={() => api.downloadExport(sessionId).catch(err => setError(err.message))}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
          >
            Export CSV
          </button>
        </div>
      </header>

      <div className="flex-1 p-6 space-y-6">
        {/* Student selector */}
        <div className="bg-white rounded-xl shadow p-4 flex items-center gap-4">
          <label htmlFor="student-select" className="text-sm font-medium text-gray-600">Student:</label>
          <select
            id="student-select"
            value={selectedStudent}
            onChange={(e) => setSelectedStudent(e.target.value)}
            aria-label="Select student to view"
            className="px-3 py-1.5 border rounded-lg text-sm"
          >
            <option value="all">All Students (Average)</option>
            {session?.students.map((s) => (
              <option key={s.student_id} value={s.student_id}>
                {s.display_name}
              </option>
            ))}
          </select>
        </div>

        {filteredReadings.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <BarChart3 className="w-12 h-12 mb-3" />
            <p className="text-lg font-medium text-gray-500">No readings recorded</p>
            <p className="text-sm">Attention data will appear here after monitoring begins.</p>
          </div>
        ) : (
          <>
            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white rounded-xl shadow p-4 text-center">
                <div className="text-sm text-gray-500 mb-1">Average</div>
                <div className="text-3xl font-bold text-blue-600">{avgAttention?.toFixed(1) ?? "—"}</div>
              </div>
              <div className="bg-white rounded-xl shadow p-4 text-center">
                <div className="text-sm text-gray-500 mb-1">Min</div>
                <div className="text-3xl font-bold text-red-500">{minAttention?.toFixed(1) ?? "—"}</div>
              </div>
              <div className="bg-white rounded-xl shadow p-4 text-center">
                <div className="text-sm text-gray-500 mb-1">Max</div>
                <div className="text-3xl font-bold text-green-500">{maxAttention?.toFixed(1) ?? "—"}</div>
              </div>
            </div>

            {/* Full timeline */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Attention Timeline
              </h2>
              <AttentionTimeline data={timelineData} showCues />
            </div>
          </>
        )}
      </div>
    </main>
  );
}
