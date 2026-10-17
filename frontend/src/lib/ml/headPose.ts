import { NormalizedLandmark } from "./faceMesh";
import { clamp, linearMap } from "../utils/mathUtils";
import { GAZE_FULL_SCORE_DEG, GAZE_ZERO_SCORE_DEG } from "./constants";

// Key landmark indices for pose estimation
const NOSE_TIP = 1;
const CHIN = 152;
const LEFT_EYE_OUTER = 33;
const RIGHT_EYE_OUTER = 263;

// Iris landmarks (with refineLandmarks: true)
const LEFT_IRIS_CENTER = 468;
const RIGHT_IRIS_CENTER = 473;
const LEFT_EYE_INNER = 133;
const RIGHT_EYE_INNER = 362;

// Canonical 3D face points in arbitrary, consistent units (x right, y down).
const POSE_POINTS = [
  { index: NOSE_TIP, point: [0, 0, 0] },
  { index: CHIN, point: [0, 0.63, -0.12] },
  { index: LEFT_EYE_OUTER, point: [-0.43, -0.32, -0.26] },
  { index: RIGHT_EYE_OUTER, point: [0.43, -0.32, -0.26] },
  { index: 61, point: [-0.28, 0.28, -0.24] },
  { index: 291, point: [0.28, 0.28, -0.24] },
];

function project(point: number[], pose: number[]) {
  const [pitch, yaw, roll, tx, ty, tz] = pose;
  const [x, y, z] = point;
  const cx = Math.cos(pitch), sx = Math.sin(pitch);
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const cz = Math.cos(roll), sz = Math.sin(roll);
  const y1 = cx * y - sx * z, z1 = sx * y + cx * z;
  const x2 = cy * x + sy * z1, z2 = -sy * x + cy * z1;
  const depth = Math.max(0.01, z2 + tz);
  return [(cz * x2 - sz * y1 + tx) / depth, (sz * x2 + cz * y1 + ty) / depth];
}

function solveLinear(matrix: number[][], rhs: number[]): number[] | null {
  const rows = matrix.map((row, i) => [...row, rhs[i]]);
  for (let col = 0; col < 6; col++) {
    let pivot = col;
    for (let row = col + 1; row < 6; row++) if (Math.abs(rows[row][col]) > Math.abs(rows[pivot][col])) pivot = row;
    [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
    const scale = rows[col][col];
    if (Math.abs(scale) < 1e-12) return null;
    for (let j = col; j <= 6; j++) rows[col][j] /= scale;
    for (let row = 0; row < 6; row++) if (row !== col) {
      const factor = rows[row][col];
      for (let j = col; j <= 6; j++) rows[row][j] -= factor * rows[col][j];
    }
  }
  return rows.map(row => row[6]);
}

export function estimateYawPitch(landmarks: NormalizedLandmark[], aspectRatio = 4 / 3): { yaw: number; pitch: number } {
  // Iterative perspective-n-point fit. Camera focal length is approximated by
  // image width; personal calibration removes the resting pose offset.
  const width = Math.abs(landmarks[RIGHT_EYE_OUTER].x - landmarks[LEFT_EYE_OUTER].x);
  if (width < 0.01) return { yaw: 0, pitch: 0 };
  const depth = 0.86 / width;
  let pose = [0, 0, 0, (landmarks[NOSE_TIP].x - 0.5) * depth, (landmarks[NOSE_TIP].y - 0.5) * depth / aspectRatio, depth];
  const observations = POSE_POINTS.flatMap(({ index }) => [landmarks[index].x - 0.5, (landmarks[index].y - 0.5) / aspectRatio]);
  const residual = (params: number[]) => POSE_POINTS.flatMap(({ point }) => project(point, params)).map((v, i) => v - observations[i]);
  let damping = 0.001;
  for (let iteration = 0; iteration < 30; iteration++) {
    const errors = residual(pose);
    const columns = pose.map((value, j) => {
      const shifted = [...pose]; shifted[j] = value + 0.0001;
      return residual(shifted).map((v, i) => (v - errors[i]) / 0.0001);
    });
    const normal = columns.map((column, i) => columns.map((other, j) => column.reduce((sum, v, k) => sum + v * other[k], 0) + (i === j ? damping : 0)));
    const rhs = columns.map(column => -column.reduce((sum, v, k) => sum + v * errors[k], 0));
    const step = solveLinear(normal, rhs);
    if (!step) break;
    const candidate = pose.map((v, i) => v + step[i]);
    if (candidate[5] <= 0.3) break;
    const loss = (values: number[]) => values.reduce((sum, v) => sum + v * v, 0);
    if (loss(residual(candidate)) < loss(errors)) { pose = candidate; damping /= 2; }
    else damping *= 4;
    if (Math.hypot(...step) < 0.00001) break;
  }
  return { yaw: clamp(pose[1] * 180 / Math.PI, -90, 90), pitch: clamp(pose[0] * 180 / Math.PI, -90, 90) };
}

function estimateGazeOffset(landmarks: NormalizedLandmark[]): number {
  // Use iris position relative to eye corners to estimate gaze direction
  if (landmarks.length <= RIGHT_IRIS_CENTER) {
    // No iris landmarks available
    return 0;
  }

  const leftIris = landmarks[LEFT_IRIS_CENTER];
  const rightIris = landmarks[RIGHT_IRIS_CENTER];
  const leftInner = landmarks[LEFT_EYE_INNER];
  const leftOuter = landmarks[LEFT_EYE_OUTER];
  const rightInner = landmarks[RIGHT_EYE_INNER];
  const rightOuter = landmarks[RIGHT_EYE_OUTER];

  // For each eye, how far is iris from center of eye (normalized)
  const leftEyeWidth = Math.abs(leftInner.x - leftOuter.x);
  const leftIrisOffset = leftEyeWidth > 0
    ? Math.abs(leftIris.x - (leftInner.x + leftOuter.x) / 2) / leftEyeWidth
    : 0;

  const rightEyeWidth = Math.abs(rightInner.x - rightOuter.x);
  const rightIrisOffset = rightEyeWidth > 0
    ? Math.abs(rightIris.x - (rightInner.x + rightOuter.x) / 2) / rightEyeWidth
    : 0;

  // Average offset, map to approximate degrees
  const avgOffset = (leftIrisOffset + rightIrisOffset) / 2;
  return avgOffset * 60; // rough mapping to degrees
}

export function computeGazeScore(landmarks: NormalizedLandmark[], baselineYaw = 0, baselinePitch = 0, aspectRatio = 4 / 3): { sGaze: number; yaw: number; pitch: number } {
  const { yaw, pitch } = estimateYawPitch(landmarks, aspectRatio);
  const irisOffset = estimateGazeOffset(landmarks);

  // Combined deviation angle
  const headDeviation = Math.hypot(yaw - baselineYaw, pitch - baselinePitch);
  const totalDeviation = Math.max(headDeviation, irisOffset);

  // Score: <15° = 1.0, >35° = 0.0, linear between
  const sGaze = linearMap(totalDeviation, GAZE_FULL_SCORE_DEG, GAZE_ZERO_SCORE_DEG, 1.0, 0.0);

  return { sGaze: clamp(sGaze, 0, 1), yaw, pitch };
}
