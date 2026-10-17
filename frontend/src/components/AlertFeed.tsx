"use client";

import { Bell } from "lucide-react";
import type { DashboardAlertData, DashboardStudentData } from "@/lib/websocket/dashboardSocket";

interface AlertFeedProps {
  alerts: DashboardAlertData[];
  students: DashboardStudentData[];
}

function getAlertLabel(type: string): string {
  switch (type) {
    case "low_attention": return "Low attention";
    case "face_not_detected": return "Face not detected";
    case "prolonged_away": return "Looking away";
    case "eyes_closed": return "Eyes closed";
    default: return type.replace(/_/g, " ");
  }
}

function getAlertColor(type: string): string {
  switch (type) {
    case "low_attention": return "bg-red-100 text-red-700 border-red-200";
    case "face_not_detected": return "bg-gray-100 text-gray-700 border-gray-200";
    case "eyes_closed": return "bg-orange-100 text-orange-700 border-orange-200";
    default: return "bg-yellow-100 text-yellow-700 border-yellow-200";
  }
}

export function AlertFeed({ alerts, students }: AlertFeedProps) {
  const studentMap = new Map(students.map((s) => [s.student_id, s.display_name]));

  return (
    <div
      role="log"
      aria-live="polite"
      aria-label="Alert feed"
      className="bg-white rounded-xl shadow p-4"
    >
      <h3 className="font-semibold text-sm text-gray-500 uppercase tracking-wider mb-3">
        Alerts
      </h3>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {alerts.length === 0 && (
          <div className="flex flex-col items-center py-6 text-gray-400">
            <Bell className="w-8 h-8 mb-2" />
            <p className="text-sm">No alerts yet</p>
          </div>
        )}
        {alerts.map((alert) => (
          <div
            key={alert.alert_id}
            className={`px-3 py-2 rounded-lg border text-sm animate-fadeIn ${getAlertColor(alert.alert_type)}`}
          >
            <span className="font-medium">
              {studentMap.get(alert.student_id) || "Unknown"}
            </span>
            {" — "}
            {getAlertLabel(alert.alert_type)}
            <span className="text-xs ml-2 opacity-60">
              {new Date(alert.triggered_at).toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
