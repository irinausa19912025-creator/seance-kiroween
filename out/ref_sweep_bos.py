# generated from sweep_bos.json — do not edit by hand
# skeleton: Sweep to Break of Structure (sweep_bos v0.2.0)
# closed_candles_only: true
# detection_conflict: skip_both
# collision_policy: overwrite

POOL_LEN = 20
WINDOW_LEN = 12


def run(bars):
    """bars: list of (time, open, high, low, close), oldest first.
    Returns a list of (time, event_name)."""
    ev = []
    pend = None
    for k, (t, o, h, l, c) in enumerate(bars):
        if pend is not None:
            if pend["side"] == "high":
                if h > pend["hi"]:
                    ev.append((t, "CANCEL")); pend = None
                elif c < pend["lo"]:
                    ev.append((t, "BOS")); pend = None
                elif (k - pend["i"]) >= WINDOW_LEN:
                    ev.append((t, "EXPIRE")); pend = None
            elif pend["side"] == "low":
                if l < pend["lo"]:
                    ev.append((t, "CANCEL")); pend = None
                elif c > pend["hi"]:
                    ev.append((t, "BOS")); pend = None
                elif (k - pend["i"]) >= WINDOW_LEN:
                    ev.append((t, "EXPIRE")); pend = None
        if k >= POOL_LEN:
            win = bars[k - POOL_LEN:k]
            ph = max(b[2] for b in win); pl = min(b[3] for b in win)
            _d0 = h > ph and c <= ph
            _d1 = l < pl and c >= pl
            _n = (1 if _d0 else 0) + (1 if _d1 else 0)
            if _n == 1:
                if _d0:
                    ev.append((t, "SWEEP_HIGH")); pend = dict(side="high", i=k, hi=h, lo=l)
                elif _d1:
                    ev.append((t, "SWEEP_LOW")); pend = dict(side="low", i=k, hi=h, lo=l)
    return ev
