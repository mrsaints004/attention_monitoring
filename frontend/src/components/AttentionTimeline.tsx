"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

interface TimelineDataPoint {
  time: string;
  attention: number | null;
  sEye?: number;
  sGaze?: number;
  sYawn?: number;
  sAffect?: number;
}

interface AttentionTimelineProps {
  data: TimelineDataPoint[];
  showCues?: boolean;
  alerts?: { time: string; type: string }[];
}

export function AttentionTimeline({ data, showCues, alerts }: AttentionTimelineProps) {
  return (
    <div className="w-full h-64">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="attention"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Attention Index"
          />
          {showCues && (
            <>
              <Line type="monotone" dataKey="sEye" stroke="#6366f1" strokeWidth={1} dot={false} name="Eye" />
              <Line type="monotone" dataKey="sGaze" stroke="#8b5cf6" strokeWidth={1} dot={false} name="Gaze" />
              <Line type="monotone" dataKey="sYawn" stroke="#f97316" strokeWidth={1} dot={false} name="Yawn" />
              <Line type="monotone" dataKey="sAffect" stroke="#ec4899" strokeWidth={1} dot={false} name="Affect" />
            </>
          )}
          {alerts?.map((a, i) => (
            <ReferenceLine key={i} x={a.time} stroke="#ef4444" strokeDasharray="3 3" label="" />
          ))}
          <ReferenceLine y={40} stroke="#f59e0b" strokeDasharray="5 5" label="Threshold" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
