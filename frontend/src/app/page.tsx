"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [mode, setMode] = useState<"choose" | "create" | "join">("choose");
  const [joinCode, setJoinCode] = useState("");
  const [instructorName, setInstructorName] = useState("");
  const [instructorEmail, setInstructorEmail] = useState("");
  const [courseName, setCourseName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    setError("");
    setLoading(true);
    try {
      const session = await api.createSession({
        instructor_name: instructorName,
        instructor_email: instructorEmail,
        course_name: courseName,
      });
      localStorage.setItem(`instructor:${session.session_id}`, session.instructor_token);
      localStorage.setItem("sessionId", session.session_id);
      localStorage.setItem("role", "instructor");
      router.push(`/console?session=${session.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    setError("");
    setLoading(true);
    try {
      const session = await api.getSessionByCode(joinCode.toUpperCase());
      localStorage.setItem("sessionId", session.session_id);
      localStorage.setItem("role", "student");
      router.push(`/join?session=${session.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid session code");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main id="main-content" role="main" className="flex-1 flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Attention Monitor</h1>
          <p className="text-gray-500">Real-time student engagement tracking for online lectures</p>
        </div>

        {mode === "choose" && (
          <div className="space-y-4">
            <button
              onClick={() => setMode("create")}
              className="w-full py-4 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors shadow-lg"
            >
              Start a Session (Instructor)
            </button>
            <button
              onClick={() => setMode("join")}
              className="w-full py-4 bg-white text-blue-600 border-2 border-blue-600 rounded-xl font-medium hover:bg-blue-50 transition-colors"
            >
              Join a Session (Student)
            </button>
          </div>
        )}

        {mode === "create" && (
          <div className="bg-white rounded-xl shadow-lg p-6 space-y-4">
            <h2 className="text-lg font-semibold">Create New Session</h2>
            <input
              type="text"
              placeholder="Your Name"
              aria-label="Instructor name"
              value={instructorName}
              onChange={(e) => setInstructorName(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <input
              type="email"
              placeholder="Email"
              aria-label="Instructor email"
              value={instructorEmail}
              onChange={(e) => setInstructorEmail(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <input
              type="text"
              placeholder="Course Name"
              aria-label="Course name"
              value={courseName}
              onChange={(e) => setCourseName(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
            {error && <p role="alert" className="text-red-500 text-sm">{error}</p>}
            <div className="flex gap-3">
              <button
                onClick={() => setMode("choose")}
                className="px-4 py-2 text-gray-500 hover:text-gray-700"
              >
                Back
              </button>
              <button
                onClick={handleCreate}
                disabled={loading || !instructorName || !instructorEmail || !courseName}
                className="flex-1 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {loading ? "Creating..." : "Create Session"}
              </button>
            </div>
          </div>
        )}

        {mode === "join" && (
          <div className="bg-white rounded-xl shadow-lg p-6 space-y-4">
            <h2 className="text-lg font-semibold">Join Session</h2>
            <input
              type="text"
              placeholder="Enter 6-character code"
              aria-label="Session join code"
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase().slice(0, 6))}
              className="w-full px-4 py-3 border rounded-lg text-center text-2xl tracking-widest font-mono focus:ring-2 focus:ring-blue-500 outline-none"
              maxLength={6}
            />
            {error && <p role="alert" className="text-red-500 text-sm">{error}</p>}
            <div className="flex gap-3">
              <button
                onClick={() => setMode("choose")}
                className="px-4 py-2 text-gray-500 hover:text-gray-700"
              >
                Back
              </button>
              <button
                onClick={handleJoin}
                disabled={loading || joinCode.length !== 6}
                className="flex-1 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {loading ? "Joining..." : "Join"}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
