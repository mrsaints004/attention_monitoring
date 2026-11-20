/** Deployment contract written only after fine-tuning and conversion checks. */
export interface AffectModelSpec {
  schema_version: 1;
  task: "daisee-affect";
  input: { shape: [number, number, 3]; color_order: "RGB"; normalization: "rgb_mean"; mean: [number, number, number] };
  labels: ["very_low", "low", "high", "very_high"];
  outputs: { engagement: number; boredom: number; confusion: number };
  crop_margin: number;
  training: { status: "fine_tuned"; dataset: "DAiSEE"; model_sha256: string };
  parity: { status: "passed"; absolute_tolerance: number };
}

export function parseAffectModelSpec(value: unknown): AffectModelSpec {
  if (!value || typeof value !== "object") throw new Error("Missing affect-model metadata");
  const spec = value as AffectModelSpec;
  const shape = spec.input?.shape;
  if (spec.schema_version !== 1 || spec.task !== "daisee-affect" ||
      spec.training?.status !== "fine_tuned" || spec.training?.dataset !== "DAiSEE" ||
      !/^[a-f0-9]{64}$/.test(spec.training?.model_sha256 ?? "") ||
      spec.parity?.status !== "passed" || spec.parity.absolute_tolerance > 0.0001 ||
      !Number.isFinite(spec.parity.absolute_tolerance) || spec.parity.absolute_tolerance < 0 ||
      spec.input?.color_order !== "RGB" || spec.input?.normalization !== "rgb_mean" ||
      !Array.isArray(shape) || shape.length !== 3 || shape[2] !== 3 ||
      !shape.slice(0, 2).every(size => Number.isInteger(size) && size > 0 && size <= 1024) ||
      !Array.isArray(spec.input.mean) || spec.input.mean.length !== 3 || !spec.input.mean.every(Number.isFinite) ||
      !Number.isFinite(spec.crop_margin) || spec.crop_margin < 0 || spec.crop_margin > 0.5 ||
      JSON.stringify(spec.labels) !== JSON.stringify(["very_low", "low", "high", "very_high"]) ||
      spec.outputs?.engagement !== 0 || spec.outputs?.boredom !== 1 || spec.outputs?.confusion !== 2) {
    throw new Error("Incompatible or unfinished DAiSEE affect model");
  }
  return spec;
}

export function expectedAffectLevel(probabilities: ArrayLike<number>): number {
  const values = Array.from(probabilities);
  if (values.length !== 4 || values.some(value => !Number.isFinite(value) || value < 0 || value > 1)) {
    throw new Error("Invalid affect probabilities");
  }
  const sum = values.reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1) > 0.01) throw new Error("Affect head must output softmax probabilities");
  return (values[1] + 2 * values[2] + 3 * values[3]) / (3 * sum);
}
