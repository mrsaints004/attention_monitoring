"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AttentionPipeline, AttentionReading, PipelineState } from "@/lib/ml/pipeline";
import type { CalibrationData } from "@/lib/ml/calibration";

export function useAttentionPipeline() {
  const pipelineRef = useRef<AttentionPipeline | null>(null);
  const [state, setState] = useState<PipelineState>("idle");
  const [calibrationProgress, setCalibrationProgress] = useState(0);
  const [latestReading, setLatestReading] = useState<AttentionReading | null>(null);

  useEffect(() => {
    const pipeline = new AttentionPipeline();
    pipelineRef.current = pipeline;

    const unsub1 = pipeline.onStateChange(setState);
    const unsub2 = pipeline.onCalibrationProgress(setCalibrationProgress);
    const unsub3 = pipeline.onReading(setLatestReading);

    return () => {
      unsub1();
      unsub2();
      unsub3();
      pipeline.stop();
    };
  }, []);

  const initialize = useCallback(async (video: HTMLVideoElement) => {
    await pipelineRef.current?.initialize(video);
  }, []);

  const startCalibration = useCallback(() => {
    pipelineRef.current?.startCalibration();
  }, []);

  const startMonitoring = useCallback(() => {
    pipelineRef.current?.startMonitoring();
  }, []);

  const pause = useCallback(() => {
    pipelineRef.current?.pause();
  }, []);

  const resume = useCallback(() => {
    pipelineRef.current?.resume();
  }, []);

  const stop = useCallback(() => {
    pipelineRef.current?.stop();
  }, []);

  const setCalibrationData = useCallback((data: CalibrationData) => {
    pipelineRef.current?.setCalibrationData(data);
  }, []);

  const getCalibrationData = useCallback((): CalibrationData | null => {
    return pipelineRef.current?.getCalibrationData() || null;
  }, []);

  const onReading = useCallback((cb: (r: AttentionReading) => void) => pipelineRef.current?.onReading(cb), []);

  return {
    state,
    calibrationProgress,
    latestReading,
    initialize,
    startCalibration,
    startMonitoring,
    pause,
    resume,
    stop,
    setCalibrationData,
    getCalibrationData,
    onReading,
  };
}
