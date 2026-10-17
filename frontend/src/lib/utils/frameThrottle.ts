export class FrameThrottle {
  private targetFps: number;
  private frameInterval: number;
  private lastFrameTime = 0;
  private rafId: number | null = null;
  private callback: (() => void) | null = null;
  private running = false;

  constructor(fps: number) {
    this.targetFps = fps;
    this.frameInterval = 1000 / fps;
  }

  setFps(fps: number) {
    this.targetFps = fps;
    this.frameInterval = 1000 / fps;
  }

  start(callback: () => void) {
    this.stop();
    this.lastFrameTime = 0;
    this.callback = callback;
    this.running = true;
    this.loop();
  }

  stop() {
    this.running = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  private loop = () => {
    if (!this.running) return;
    this.rafId = requestAnimationFrame((now) => {
      if (now - this.lastFrameTime >= this.frameInterval) {
        this.lastFrameTime = now;
        this.callback?.();
      }
      this.loop();
    });
  };
}
