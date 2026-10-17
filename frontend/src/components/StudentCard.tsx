"use client";

import Link from "next/link";

interface StudentCardProps {
  studentId: string;
  displayName: string;
  attentionIndex: number | null;
  qualityFlag: string;
  sessionId: string;
}

function getCardColor(index: number | null, flag: string): string {
  if (index === null || flag !== "normal") return "border-gray-300 bg-gray-50";
  if (index > 70) return "border-green-300 bg-green-50";
  if (index > 40) return "border-yellow-300 bg-yellow-50";
  return "border-red-300 bg-red-50";
}

function getDotColor(index: number | null, flag: string): string {
  if (index === null || flag !== "normal") return "bg-gray-400";
  if (index > 70) return "bg-green-500";
  if (index > 40) return "bg-yellow-500";
  return "bg-red-500";
}

export function StudentCard({ studentId, displayName, attentionIndex, qualityFlag, sessionId }: StudentCardProps) {
  const status = qualityFlag !== "normal" || attentionIndex === null ? qualityFlag.replace(/_/g, " ") : attentionIndex > 70 ? "Attentive" : attentionIndex > 40 ? "At-Risk" : "Disengaged";
  const scoreText = qualityFlag === "normal" ? `${Math.round(attentionIndex ?? 0)}%` : qualityFlag.replace(/_/g, " ");

  return (
    <Link
      href={`/student-detail/${studentId}?session=${sessionId}`}
      aria-label={`${displayName} — ${scoreText}`}
      className="block rounded-lg focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
    >
      <div className={`p-4 rounded-lg border-2 ${getCardColor(attentionIndex, qualityFlag)} hover:shadow-md transition-shadow cursor-pointer`}>
        <div className="flex items-center justify-between mb-2">
          <span className="font-medium text-sm truncate">{displayName}</span>
          <span className={`w-3 h-3 rounded-full ${getDotColor(attentionIndex, qualityFlag)}`} />
        </div>
        <div className="text-2xl font-bold">
          {qualityFlag === "normal" ? `${Math.round(attentionIndex ?? 0)}%` : "--"}
        </div>
        <span className="text-xs text-gray-700 capitalize">{status}</span>
      </div>
    </Link>
  );
}
