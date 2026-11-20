"use client";
import { useEffect, useRef, useState, type RefObject } from "react";
import { loadPilotModel, type PilotModel, type PilotPrediction } from "@/lib/ml/pilotScoring";

const levels = ["Very low", "Low", "High", "Very high"];

export function PilotEngagement({ video, enabled, evidenceTimestamp }: {
  video: RefObject<HTMLVideoElement | null>; enabled: boolean; evidenceTimestamp: number;
}) {
  const evidence = useRef(evidenceTimestamp);
  useEffect(() => { evidence.current = evidenceTimestamp; }, [evidenceTimestamp]);
  const [prediction, setPrediction] = useState<PilotPrediction | null>(null);
  const [status, setStatus] = useState("Waiting for reliable camera monitoring");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let model: PilotModel | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let busy = false;
    const update = async () => {
      if (cancelled) return;
      busy = true;
      try {
        if (document.hidden || Date.now() - evidence.current > 1500 || !video.current || video.current.readyState < 2) {
          setPrediction(null); setStatus("Waiting for a visible camera frame");
        } else {
          const value = await model!.predict(video.current);
          if (!cancelled) { setPrediction(value); setStatus("Live engagement prediction"); }
        }
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Pilot inference failed");
        cancelled = true;
      } finally {
        busy = false;
        if (cancelled) model?.dispose();
        else timer = setTimeout(() => void update(), 500);
      }
    };
    void (async () => {
      try {
        setPrediction(null); setError(""); setStatus("Loading trained DAiSEE pilot…");
        model = await loadPilotModel();
        if (cancelled) { model.dispose(); return; }
        await update();
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Pilot could not load");
      }
    })();
    return () => { cancelled = true; clearTimeout(timer); if (!busy) model?.dispose(); };
  }, [enabled, video, attempt]);
  const current = enabled && !error ? prediction : null;
  return <section aria-labelledby="pilot-heading" className="rounded-xl border border-gray-200 bg-white p-4 sm:p-6">
    <h2 id="pilot-heading" className="text-lg font-semibold text-gray-900">DAiSEE engagement pilot</h2>
    <p className="mt-1 text-sm text-gray-700">Trained on 4 clips, validated on 4, tested on 4. Test accuracy: 25% (1 of 4).</p>
    <p role="status" className="mt-3 text-sm text-gray-700">{enabled ? status : "Paused until monitoring has a reliable camera frame"}</p>
    {error && enabled && <div role="alert" className="mt-3 text-sm text-red-800">
      {error}<button onClick={() => setAttempt(value => value + 1)} className="ml-3 min-h-10 rounded border px-3 focus-visible:outline-2 focus-visible:outline-blue-600">Retry pilot</button>
    </div>}
    {current && <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <p className="text-2xl font-semibold tabular-nums text-gray-900">{levels[current.predictedLevel]}<span className="ml-2 text-sm font-normal">predicted engagement</span></p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">{current.probabilities.map((value, index) => <div key={levels[index]} className="flex justify-between gap-2"><dt>{levels[index]}</dt><dd className="tabular-nums">{(value * 100).toFixed(1)}%</dd></div>)}</dl>
    </div>}
    <p className="mt-3 text-sm text-gray-700">Engagement-only experiment shown separately from the Attention Index. Boredom and confusion were not trained. <a className="inline-flex min-h-10 items-center underline focus-visible:outline-2 focus-visible:outline-blue-600" href="/dataset-review">View measured results</a></p>
  </section>;
}
