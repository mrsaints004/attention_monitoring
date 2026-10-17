"use client";

interface CueBreakdownProps {
  affectAvailable?: boolean;
  sEye: number;
  sGaze: number;
  sYawn: number;
  sAffect: number;
}

const cues = [
  { key: "sEye" as const, label: "Eye Openness", color: "bg-blue-500" },
  { key: "sGaze" as const, label: "Gaze Direction", color: "bg-purple-500" },
  { key: "sYawn" as const, label: "Yawn State", color: "bg-orange-500" },
  { key: "sAffect" as const, label: "Expression", color: "bg-pink-500" },
];

export function CueBreakdown({ sEye, sGaze, sYawn, sAffect, affectAvailable = false }: CueBreakdownProps) {
  const scores = { sEye, sGaze, sYawn, sAffect };

  return (
    <div className="space-y-3">
      {!affectAvailable && <p className="text-sm text-gray-600">Facial affect unavailable. This score uses three geometric cues.</p>}
      {cues.filter(cue => cue.key !== "sAffect" || affectAvailable).map(({ key, label, color }) => (
        <div key={key}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">{label}</span>
            <span className="font-medium">{(scores[key] * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`${color} h-2 rounded-full transition-all duration-300`}
              style={{ width: `${scores[key] * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
