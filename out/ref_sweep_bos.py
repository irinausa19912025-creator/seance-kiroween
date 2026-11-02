# generated from sweep_bos.json — do not edit by hand
POOL_LEN = 20
WINDOW   = 12

def run(bars):
    """bars: list of (time, o, h, l, c), oldest first. Returns a list of (time, event)."""
    ev = []
    pend = None          # dict(side, i, hi, lo)
    for k, (t, o, h, l, c) in enumerate(bars):
        if pend is not None:
            if pend["side"] == 1:
                if h > pend["hi"]:
                    ev.append((t, "CANCEL")); pend = None
                elif c < pend["lo"]:
                    ev.append((t, "BOS")); pend = None
                elif k - pend["i"] >= WINDOW:
                    ev.append((t, "EXPIRE")); pend = None
            else:
                if l < pend["lo"]:
                    ev.append((t, "CANCEL")); pend = None
                elif c > pend["hi"]:
                    ev.append((t, "BOS")); pend = None
                elif k - pend["i"] >= WINDOW:
                    ev.append((t, "EXPIRE")); pend = None
        if k >= POOL_LEN:
            win = bars[k - POOL_LEN:k]
            ph = max(b[2] for b in win); pl = min(b[3] for b in win)
            sh = h > ph and c <= ph
            sl = l < pl and c >= pl
            if sh and not sl:
                ev.append((t, "SWEEP_HIGH")); pend = dict(side=1, i=k, hi=h, lo=l)
            elif sl and not sh:
                ev.append((t, "SWEEP_LOW"));  pend = dict(side=2, i=k, hi=h, lo=l)
    return ev
