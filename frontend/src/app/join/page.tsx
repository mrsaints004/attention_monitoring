"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, SessionInfo } from "@/lib/api";
import { useCamera } from "@/hooks/useCamera";
import { useAttentionPipeline } from "@/hooks/useAttentionPipeline";
import { ConsentForm } from "@/components/ConsentForm";
import { CalibrationOverlay } from "@/components/CalibrationOverlay";
import { XCircle } from "lucide-react";

type Step = "consent" | "details" | "camera" | "calibrating";

function JoinPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session") || "";
  const { videoRef, hasPermission, error: cameraError, startCamera } = useCamera();
  const { state, calibrationProgress, initialize, startCalibration, getCalibrationData, stop } = useAttentionPipeline();

  const [step, setStep] = useState<Step>("consent");
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (sessionId) {
      api.getSession(sessionId).then(s => { if (s.ended_at) setError("This session has ended. Return home to join a new session."); setSession(s); }).catch(() => setError("Session not found. Return home and check the join code."));
    }
  }, [sessionId]);

  const handleConsent = () => { sessionStorage.setItem(`consent:${sessionId}`, "v1"); setStep("details"); };

  const handleJoin = async () => {
    if (!displayName.trim()) return;
    setError(""); setBusy(true);
    try {
      const result = await api.joinSession(sessionId, {
        display_name: displayName,
        device_token: localStorage.getItem(`device:${sessionId}`) || undefined,
      });
      localStorage.setItem(`student:${sessionId}`, result.student_id);
      localStorage.setItem(`device:${sessionId}`, result.device_token);
      setStep("camera");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to join");
    } finally { setBusy(false); }
  };

  const handleCameraReady = useCallback(async () => {
    await startCamera();
  }, [startCamera]);

  useEffect(() => {
    if (step === "camera" && hasPermission === null) {
      handleCameraReady();
    }
  }, [step, hasPermission, handleCameraReady]);

  const handleStartCalibration = async () => {
    if (videoRef.current) {
      try {
        setError(""); setBusy(true);
        await initialize(videoRef.current);
        startCalibration();
        setStep("calibrating");
      } catch (err) { setError(err instanceof Error ? err.message : "Could not load camera analysis. Try again."); }
      finally { setBusy(false); }
    }
  };

  useEffect(() => {
    if (state === "idle" && step === "calibrating" && calibrationProgress >= 1) {
      // Save calibration data so the lecture page can restore it
      const calData = getCalibrationData();
      if (calData) {
        sessionStorage.setItem(`calibration:${sessionId}`, JSON.stringify(calData));
      }
      const studentId = localStorage.getItem(`student:${sessionId}`);
      router.push(`/lecture?session=${sessionId}&student=${studentId}`);
    }
  }, [state, step, calibrationProgress, sessionId, router, getCalibrationData]);

  return (
    <main id="main-content" role="main" className="flex-1 flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      {step === "calibrating" && <CalibrationOverlay progress={calibrationProgress} onRetry={startCalibration} onCancel={() => { stop(); setStep("camera"); }} />}

      {step === "consent" && <div className="space-y-4">{error && <p role="alert" className="text-red-800">{error}</p>}<ConsentForm onConsent={handleConsent} /></div>}

      {step === "details" && (
        <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">
            Join: {session?.course_name || "Loading..."}
          </h2>
          {session && (
            <p className="text-sm text-gray-500">
              Instructor: {session.instructor_name}
            </p>
          )}
          <label htmlFor="display-alias" className="block text-sm font-medium">Display alias (use a nickname)</label>
          <input
            id="display-alias" maxLength={255}
            type="text"
            placeholder="Choose a nickname"
            aria-label="Display name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          />
          {error && (
            <div role="alert" className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <XCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}
          <button
            onClick={handleJoin}
            disabled={busy || !session || !!session.ended_at || !displayName.trim()}
            aria-label="Continue to camera setup"
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? "Joining…" : "Continue"}
          </button>
        </div>
      )}

      {(step === "camera" || step === "calibrating") && (
        <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Camera Setup</h2>
          <div className="relative aspect-video bg-gray-900 rounded-lg overflow-hidden">
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              autoPlay
              playsInline
              muted
              style={{ transform: "scaleX(-1)" }}
            />
          </div>
          {error && <p role="alert" className="text-red-700">{error}</p>}
          {cameraError && (
            <div role="alert" className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <XCircle className="w-4 h-4 flex-shrink-0" />
              {cameraError}
            </div>
          )}
          {hasPermission === false && <button onClick={startCamera} className="underline px-3 py-2">Retry camera access</button>}
          {hasPermission === false && (
            <div role="alert" className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              <XCircle className="w-4 h-4 flex-shrink-0" />
              Camera access is required for attention monitoring. Please grant permission and try again.
            </div>
          )}
          {hasPermission && step === "camera" && (
            <button
              disabled={busy}
              onClick={handleStartCalibration}
              aria-label="Start camera calibration"
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              {busy ? "Loading camera analysis…" : "Start Calibration"}
            </button>
          )}
        </div>
      )}
    </main>
  );
}

export default function JoinPage() {
  return (
    <Suspense fallback={<div className="flex-1 flex items-center justify-center">Loading...</div>}>
      <JoinPageContent />
    </Suspense>
  );
}
