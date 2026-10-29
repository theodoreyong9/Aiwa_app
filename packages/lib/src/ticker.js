// A repeating background task, one run at a time: a tick that arrives while the previous run is still going (a slow
// device, a long proof) is skipped, never stacked.

export class Ticker {
  start(intervalMs, task, onError) {
    this.stop();
    this._timer = setInterval(() => {
      if (this._busy) return;
      this._busy = true;
      Promise.resolve().then(task).catch((err) => onError?.(err)).finally(() => { this._busy = false; });
    }, intervalMs);
  }

  stop() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  }
}
