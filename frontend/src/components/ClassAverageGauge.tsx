"use client";

interface ClassAverageGaugeProps {
  average: number | null;
  studentCount: number;
}

function getGaugeColor(avg: number): string {
  if (avg > 70) return "text-green-500";
  if (avg > 40) return "text-yellow-500";
  return "text-red-500";
}

function getProgressColor(avg: number): string {
  if (avg > 70) return "stroke-green-500";
  if (avg > 40) return "stroke-yellow-500";
  return "stroke-red-500";
}

export function ClassAverageGauge({ average, studentCount }: ClassAverageGaugeProps) {
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - ((average ?? 0) / 100) * circumference;

  return (
    <div
      role="status"
      aria-label={`Class average: ${(average === null ? "—" : Math.round(average))} out of 100 with ${studentCount} student${studentCount !== 1 ? "s" : ""}`}
      className="flex flex-col items-center p-4 bg-white rounded-xl shadow"
    >
      <div className="relative w-32 h-32">
        <svg className="w-32 h-32 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="45" fill="none" stroke="#e5e7eb" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="45" fill="none"
            className={getProgressColor(average ?? 0)}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 0.5s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-3xl font-bold ${getGaugeColor(average ?? 0)}`}>
            {(average === null ? "—" : Math.round(average))}
          </span>
          <span className="text-xs text-gray-400">/ 100</span>
        </div>
      </div>
      <div className="mt-2 text-sm text-gray-500">
        {average === null ? "No reliable readings" : "Class Average"} ({studentCount} student{studentCount !== 1 ? "s" : ""})
      </div>
    </div>
  );
}
