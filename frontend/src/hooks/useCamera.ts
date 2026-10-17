"use client";
import { useCallback, useEffect, useRef, useState } from "react";
export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const generation = useRef(0);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startCamera = useCallback(async () => {
    if (streamRef.current?.getVideoTracks().some(t => t.readyState === "live")) return;
    const current = ++generation.current;
    try {
      if (!navigator.mediaDevices) throw new Error("Camera access requires HTTPS or localhost.");
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      if (current !== generation.current) { stream.getTracks().forEach(t => t.stop()); return; }
      streamRef.current = stream; setMediaStream(stream);
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      setHasPermission(true); setError(null);
    } catch (err) {
      if (current !== generation.current) return;
      setHasPermission(false); setError(err instanceof Error ? err.message : "Camera access denied");
    }
  }, []);
  const attachToVideo = useCallback((video: HTMLVideoElement) => { if (streamRef.current) { video.srcObject = streamRef.current; void video.play().catch(() => {}); } }, []);
  const stopCamera = useCallback(() => {
    generation.current++;
    streamRef.current?.getTracks().forEach(t => t.stop()); streamRef.current = null; setMediaStream(null);
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);
  useEffect(() => stopCamera, [stopCamera]);
  return { mediaStream, videoRef, stream: streamRef, hasPermission, error, startCamera, stopCamera, attachToVideo };
}
