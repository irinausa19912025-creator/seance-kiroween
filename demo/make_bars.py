#!/usr/bin/env python3
"""Deterministic synthetic candles for the Seance reproducible example.

No market data, no third-party rights: every bar is produced by this file
from a fixed seed, so anyone running it gets a byte-identical TSV.

    python3 demo/make_bars.py [out.tsv] [bars] [seed]

Output matches the format the plain MQL5 expert and the Python reference
both read: time<TAB>open<TAB>high<TAB>low<TAB>close<TAB>tick_volume,
time as YYYY.MM.DD HH:MM, one hour per bar. Standard library only.
"""
import sys, random, datetime

out   = sys.argv[1] if len(sys.argv) > 1 else "demo/synthetic_bars.tsv"
nbars = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
seed  = int(sys.argv[3]) if len(sys.argv) > 3 else 20261104

rnd = random.Random(seed)
t = datetime.datetime(2024, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
price = 1.10000
rows = []
for i in range(nbars):
    # drift changes slowly, so the series makes real swings instead of noise
    drift = 0.00012 * rnd.choice((-1, -1, 0, 1, 1)) if i % 17 == 0 else 0.0
    o = price
    step = rnd.gauss(drift, 0.00060)
    c = round(o + step, 5)
    wick_up = abs(rnd.gauss(0, 0.00045))
    wick_dn = abs(rnd.gauss(0, 0.00045))
    h = round(max(o, c) + wick_up, 5)
    l = round(min(o, c) - wick_dn, 5)
    v = 500 + int(abs(step) * 2_000_000)
    rows.append((t.strftime("%Y.%m.%d %H:%M"), o, h, l, c, v))
    price = c
    t += datetime.timedelta(hours=1)

with open(out, "w") as f:
    f.write("time\topen\thigh\tlow\tclose\ttick_volume\n")
    for r in rows:
        f.write("%s\t%.5f\t%.5f\t%.5f\t%.5f\t%d\n" % r)
print(f"written {out}: {len(rows)} bars, seed {seed}")
