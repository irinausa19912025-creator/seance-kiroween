import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent/"out"))
import ref_sweep_bos as ref

base = pathlib.Path(__file__).resolve().parent.parent
rows = (base/"out/seance_bars.tsv").read_text(encoding="utf-8-sig").split("\n")
bars = []
for r in rows[1:]:
    p = r.split("\t")
    if len(p) < 5: continue
    bars.append((p[0], float(p[1]), float(p[2]), float(p[3]), float(p[4])))
py = ref.run(bars)

mq = []
for r in (base/"out/mql5_events.tsv").read_text(encoding="utf-8-sig").split("\n"):
    p = r.split("\t")
    if len(p) == 2 and p[1]: mq.append((p[0], p[1]))

print(f"эталон Python : {len(py)} событий")
print(f"MQL5          : {len(mq)} событий")
diff = []
for i in range(max(len(py), len(mq))):
    a = py[i] if i < len(py) else None
    b = mq[i] if i < len(mq) else None
    if a != b: diff.append((i, a, b))
print(f"расхождений   : {len(diff)}")
for i, a, b in diff[:10]:
    print(f"  #{i}  python={a}  mql5={b}")
from collections import Counter
print("по типам python:", dict(Counter(e for _, e in py)))
print("по типам mql5  :", dict(Counter(e for _, e in mq)))
