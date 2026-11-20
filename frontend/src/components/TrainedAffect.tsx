import Link from "next/link";
import type { AttentionReading } from "@/lib/ml/pipeline";

export function TrainedAffect({ reading, running }: { reading: AttentionReading | null; running: boolean }) {
  const reliable = running && reading?.qualityFlag === "normal" && reading.affectAvailable;
  const values = reliable ? [reading.sAffect, reading.boredom, reading.confusion] : [];
  return <section aria-labelledby="affect-heading" className="rounded-xl border border-gray-200 bg-white p-5">
    <h2 id="affect-heading" className="text-lg font-semibold">DAiSEE facial-affect estimates</h2>
    <p className="mt-1 text-sm text-gray-600">Face-pretrained MobileNet, fine-tuned on the full labelled DAiSEE training partition.</p>
    {reliable ? <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
      {["Engagement", "Boredom", "Confusion"].map((label, i) => <div key={label} className="rounded-lg bg-gray-50 p-4">
        <dt className="text-sm text-gray-600">{label}</dt>
        <dd className="mt-1 text-2xl font-semibold tabular-nums">{typeof values[i] === "number" && Number.isFinite(values[i]) ? `${Math.round(values[i]! * 100)}/100` : "Unavailable"}</dd>
      </div>)}
    </dl> : <p role="status" className="mt-4 rounded-lg bg-gray-50 p-4 text-sm">{!running ? "Monitoring is paused or starting." : reading?.affectAvailable ? "Waiting for a reliable face image." : "Facial-affect estimates unavailable. Geometric monitoring remains available."}</p>}
    <p className="mt-3 text-sm leading-6 text-gray-600">Scores show expected intensity across four trained levels, not confidence percentages. Engagement contributes to the Attention Index; boredom and confusion are reported separately. <Link className="inline-flex min-h-10 items-center underline" href="/dataset-review">View measured model results</Link></p>
  </section>;
}
