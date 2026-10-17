"use client";

import { useEffect, useRef } from "react";

interface SelfViewProps {
  stream: MediaStream | null;
}

export function SelfView({ stream }: SelfViewProps) {
  const localRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (localRef.current && stream) {
      localRef.current.srcObject = stream;
      localRef.current.play().catch(() => {});
    }
  }, [stream]);

  return (
    <div
      aria-label="Your camera preview"
      className="relative w-24 h-20 sm:w-32 sm:h-24 md:w-40 md:h-32 rounded-lg overflow-hidden border-2 border-gray-300 shadow-lg"
    >
      <video
        ref={localRef}
        className="w-full h-full object-cover"
        autoPlay
        playsInline
        muted
        style={{ transform: "scaleX(-1)" }}
      />
    </div>
  );
}
