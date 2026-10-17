"use client";

import { useState } from "react";

interface ConsentFormProps {
  onConsent: () => void;
}

export function ConsentForm({ onConsent }: ConsentFormProps) {
  const [agreed, setAgreed] = useState(false);

  return (
    <div className="max-w-lg mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-xl font-semibold mb-4">Consent to Monitoring</h2>
      <div className="text-sm text-gray-600 space-y-3 mb-6">
        <p>
          This lecture uses a real-time attention monitoring system to help your instructor
          understand class engagement levels. By joining, you consent to the following:
        </p>
        <ul className="list-disc ml-5 space-y-1">
          <li>Your webcam will be used to analyze facial cues (eye state, head pose, expressions)</li>
          <li>All processing happens locally in your browser — no video is recorded or transmitted</li>
          <li>Scores, quality states, timestamps and your chosen display alias are stored on the server</li>
          <li>Your instructor can see individual scores, class summaries and alerts, but cannot see your webcam feed</li>
          <li>You can pause monitoring at any time using the pause button</li>
        </ul>
        <p>
          Use a nickname rather than your name or matriculation number. Scores are experimental
          teaching aids and must not be used for grading or discipline. You may pause or leave
          at any time. Ask the session organiser about retention and deletion before joining.
        </p>
      </div>
      <label className="flex items-start gap-3 mb-4 cursor-pointer">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-0.5 w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm text-gray-700">
          I have read and agree to the monitoring terms above
        </span>
      </label>
      <button
        onClick={onConsent}
        disabled={!agreed}
        className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        I Understand and Consent
      </button>
    </div>
  );
}
