"use client";

import { Users } from "lucide-react";
import { StudentCard } from "./StudentCard";
import type { DashboardStudentData } from "@/lib/websocket/dashboardSocket";

interface StudentGridProps {
  students: DashboardStudentData[];
  sessionId: string;
}

export function StudentGrid({ students, sessionId }: StudentGridProps) {
  if (students.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-400">
        <Users className="w-12 h-12 mb-3" />
        <p className="text-lg font-medium text-gray-500">No students yet</p>
        <p className="text-sm">Students will appear here when they join the session.</p>
      </div>
    );
  }

  return (
    <div
      aria-label="Student attention grid"
      className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"
    >
      {students.map((s) => (
        <StudentCard
          key={s.student_id}
          studentId={s.student_id}
          displayName={s.display_name}
          attentionIndex={s.attention_index}
          qualityFlag={s.quality_flag}
          sessionId={sessionId}
        />
      ))}
    </div>
  );
}
