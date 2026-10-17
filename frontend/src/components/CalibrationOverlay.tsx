"use client";
import { useEffect, useRef } from "react";
interface CalibrationOverlayProps { progress: number; onRetry?: () => void; onCancel?: () => void; }
export function CalibrationOverlay({ progress, onRetry, onCancel }: CalibrationOverlayProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current; const previous = document.activeElement as HTMLElement | null;
    dialog?.showModal(); return () => { dialog?.close(); previous?.focus(); };
  }, []);
  const percent = Math.round(progress * 100);
  return <dialog ref={ref} aria-labelledby="calibration-title" onCancel={event => { event.preventDefault(); onCancel?.(); }} className="m-auto w-full max-w-md rounded-xl bg-white p-8 text-center shadow-xl backdrop:bg-black/70">
    <h2 id="calibration-title" className="text-xl font-semibold mb-2">Calibrating</h2>
    <p className="text-gray-700 mb-6">Look at the screen with your eyes open. Keep one face in view with good lighting for at least five seconds.</p>
    <progress value={percent} max={100} aria-label="Camera calibration" className="w-full mb-4" />
    <p className="text-sm text-gray-700" aria-live="polite">{percent}% complete</p>
    {onRetry && <button onClick={onRetry} className="mt-4 text-sm text-blue-700 underline">Restart calibration</button>}
    {onCancel && <button autoFocus onClick={onCancel} className="ml-3 mt-4 text-sm text-gray-700 underline">Back to camera setup</button>}
  </dialog>;
}
