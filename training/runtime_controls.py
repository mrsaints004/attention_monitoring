"""Optional execution pacing without changing the training experiment."""
import os
import time


def epoch_cooldown(environ=None, sleep=None):
    environ = os.environ if environ is None else environ
    sleep = time.sleep if sleep is None else sleep
    seconds = int(environ.get('DAISEE_EPOCH_COOLDOWN_SECONDS', '0'))
    if not 0 <= seconds <= 3600:
        raise ValueError('DAISEE_EPOCH_COOLDOWN_SECONDS must be between 0 and 3600')
    if seconds:
        print(f'Cooling break: {seconds} seconds. Epoch checkpoint is saved; Ctrl+C is safe.', flush=True)
        remaining = seconds
        while remaining:
            interval = min(30, remaining)
            sleep(interval)
            remaining -= interval
        print('Cooling break complete; continuing.', flush=True)
