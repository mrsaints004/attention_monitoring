// Fusion weights
export const W_EYE = 0.30;
export const W_GAZE = 0.25;
export const W_YAWN = 0.20;
export const W_AFFECT = 0.25;

// EMA smoothing
export const EMA_ALPHA = 0.3;

// Frame rates
export const PIPELINE_FPS = 10;
export const AFFECT_FPS = 3;

// Calibration
export const CALIBRATION_FRAMES = 50;
export const CALIBRATION_DURATION_MS = 5000;
export const CALIBRATION_TIMEOUT_MS = 15000;
export const RECALIBRATE_AFTER_ABSENCE_MS = 30000;

// Eye state
export const EAR_CLOSED_RATIO = 0.75;
export const BLINK_MAX_DURATION_MS = 400;
export const EYE_WINDOW_MS = 2000;
export const EYES_CLOSED_CAP_SECONDS = 3;
export const EYES_CLOSED_CAP_INDEX = 15;

// Head pose / gaze
export const GAZE_FULL_SCORE_DEG = 15;
export const GAZE_ZERO_SCORE_DEG = 35;

// Yawn
export const MAR_YAWN_OFFSET = 0.35;
export const YAWN_MIN_DURATION_MS = 1500;
export const YAWN_RECOVERY_MS = 10000;

// Quality
export const LOW_CONFIDENCE_THRESHOLD = 0.5;

// Adaptive FPS
export const FRAME_SLOW_THRESHOLD_MS = 150;
export const FRAME_DISABLE_AFFECT_THRESHOLD_MS = 300;

// WebSocket batching
export const WS_BATCH_INTERVAL_MS = 500;
