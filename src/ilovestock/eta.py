"""Estimate remaining time from progress within a phase."""

MIN_DONE = 2


def estimate_eta(phase_started: float | None, now: float, done: int, total: int) -> float | None:
    if total <= 0 or done < MIN_DONE or phase_started is None:
        return None
    if done >= total:
        return 0.0
    return max(0.0, (now - phase_started) / done * (total - done))
