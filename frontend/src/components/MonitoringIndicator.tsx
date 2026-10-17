"use client";

import type { QualityFlag } from "@/lib/ml/qualityFlags";

interface MonitoringIndicatorProps {
  attentionIndex: number | null;
  qualityFlag: QualityFlag;
}

function getColor(index: number | null, flag: QualityFlag): string {
  if (index === null || flag !== "normal") return "bg-gray-400";
  if (index > 70) return "bg-green-500";
  if (index > 40) return "bg-yellow-500";
  return "bg-red-500";
}

function getLabel(flag: QualityFlag): string {
  switch (flag) {
    case "face_not_detected": return "Face not detected";
    case "away": return "Away";
    case "low_confidence": return "Low confidence";
    case "tab_inactive": return "Tab inactive";
    case "monitoring_paused": return "Paused";
    default: return "Monitoring";
  }
}

export function MonitoringIndicator({ attentionIndex, qualityFlag }: MonitoringIndicatorProps) {
  const color = getColor(attentionIndex, qualityFlag);

  const label = qualityFlag === "normal" && attentionIndex !== null
    ? `Attention: ${Math.round(attentionIndex ?? 0)}%`
    : getLabel(qualityFlag);

  return (
    <div
      role="status"
      aria-label={label}
      className="flex items-center gap-2 px-3 py-1.5 bg-white/90 rounded-full shadow text-sm"
    >
      <span className={`w-3 h-3 rounded-full ${color} animate-pulse`} />
      <span className="text-gray-700">{label}</span>
    </div>
  );
}
