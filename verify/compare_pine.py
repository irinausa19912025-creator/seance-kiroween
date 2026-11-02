# Seance verification harness: count reference events inside a time window,
# so the Pine implementation (which can only report counters) can be compared
# against the Python reference on identical exchange candles.
import sys, datetime, importlib.util
spec = importlib.util.spec_from_file_location("ref", sys.argv[1])
ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
tsv, start_s, end_s = sys.argv[2], sys.argv[3], sys.argv[4]
def ms(s):
    return int(datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
               .replace(tzinfo=datetime.timezone.utc).timestamp()*1000)
a, b = ms(start_s), ms(end_s)
bars = []
for i, line in enumerate(open(tsv)):
    if i == 0: continue
    t, o, h, l, c = line.split()
    bars.append((int(t), float(o), float(h), float(l), float(c)))
ev = ref.run(bars)
inw = [e for e in ev if a <= e[0] <= b]
names = ["SWEEP_HIGH", "SWEEP_LOW", "BOS", "CANCEL", "EXPIRE"]
print(f"bars loaded     {len(bars)}")
print(f"window          {start_s} .. {end_s} UTC")
nb = sum(1 for x in bars if a <= x[0] <= b)
print(f"bars in window  {nb}")
for n in names:
    print(f"{n:<12} {sum(1 for e in inw if e[1]==n)}")
print(f"{'TOTAL':<12} {len(inw)}")
