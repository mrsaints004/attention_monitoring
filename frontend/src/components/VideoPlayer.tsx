"use client";
import { useEffect, useRef } from "react";
import { Track } from "livekit-client";
export function VideoPlayer({ track, placeholder, muted = false }: { track?: Track; placeholder?: boolean; muted?: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (!track || !element) return;
    track.attach(element);
    return () => { track.detach(element); };
  }, [track]);
  return <div className="relative aspect-video rounded-lg overflow-hidden bg-gray-900">
    <video ref={ref} autoPlay playsInline muted={muted} controls className="w-full h-full" />
    {(placeholder || !track) && <p role="status" className="absolute inset-0 flex items-center justify-center text-gray-200">Waiting for instructor video or slides…</p>}
  </div>;
}
