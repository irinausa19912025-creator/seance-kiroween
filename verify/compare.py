#!/usr/bin/env python3
"""Compare the Python reference event stream against an MQL5 event stream.

Exit codes
  0  AGREE          - identical events, in the same order, on the same bar times
  1  DISAGREE       - at least one event differs; the first divergence is named
  2  SETUP MISMATCH - the two sides did not read comparable input, or a file is
                      missing or malformed. Not a logic result.

Standard library only. Run from the repository root.
"""
import sys, pathlib, difflib, importlib.util
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEF_BARS = ROOT / "out" / "seance_bars.tsv"
DEF_MQL5 = ROOT / "out" / "mql5_events.tsv"
DEF_REF = ROOT / "out" / "ref_sweep_bos.py"

SWEEPS = ("SWEEP_HIGH", "SWEEP_LOW")
RESOLUTIONS = ("BOS", "CANCEL", "EXPIRE")


def die_setup(msg, hint=None):
    print("VERDICT: SETUP MISMATCH - the two sides are not comparable.")
    print(f"  {msg}")
    if hint:
        print(f"  likely cause: {hint}")
    sys.exit(2)


def load_bars(path):
    if not path.exists():
        die_setup(f"bars file not found: {path}",
                  "run build.sh and make sure the recorded bars are present")
    bars, skipped_header = [], False
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        f = line.split("\t")
        if len(f) < 5:
            die_setup(f"{path}:{n} has {len(f)} tab-separated fields, expected at least 5",
                      "the bars file must be TAB separated: time, open, high, low, close")
        if n == 1 and not _isnum(f[1]):
            skipped_header = True
            continue
        try:
            bars.append((f[0], float(f[1]), float(f[2]), float(f[3]), float(f[4])))
        except ValueError:
            die_setup(f"{path}:{n} has a non-numeric price field: {f[1:5]}",
                      "a header row that was not recognised, or a corrupted line")
    if not bars:
        die_setup(f"{path} contains no bars")
    return bars, skipped_header


def _isnum(s):
    try:
        float(s); return True
    except ValueError:
        return False


def load_events(path):
    if not path.exists():
        die_setup(f"event file not found: {path}",
                  "the MQL5 expert writes into the terminal's Files folder; copy its "
                  "output here, or pass the path as the second argument")
    ev = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        f = line.split("\t")
        if len(f) != 2:
            die_setup(f"{path}:{n} has {len(f)} fields, expected 2 (time, event)")
        ev.append((f[0], f[1]))
    return ev


def load_reference(path):
    if not path.exists():
        die_setup(f"generated reference not found: {path}", "run build.sh first")
    spec = importlib.util.spec_from_file_location("seance_ref", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sweep_accounting(events):
    """Every sweep must end in exactly one resolution, or be open at the feed's end.

    A sweep that is replaced by the next sweep without a resolution is reported
    as ORPHANED: the observation was silently discarded.
    """
    orphans, open_at_end, pending = [], None, None
    for t, e in events:
        if e in RESOLUTIONS:
            pending = None
        elif e in SWEEPS:
            if pending is not None:
                orphans.append(pending)
            pending = (t, e)
    if pending is not None:
        open_at_end = pending
    return orphans, open_at_end


def main(argv):
    if "--self-test" in argv:
        return self_test()

    bars_path = pathlib.Path(argv[1]) if len(argv) > 1 else DEF_BARS
    mql5_path = pathlib.Path(argv[2]) if len(argv) > 2 else DEF_MQL5

    bars, had_header = load_bars(bars_path)
    ref = load_reference(DEF_REF)
    py = [(t, e) for t, e in ref.run(bars)]
    mq = load_events(mql5_path)

    print("SEANCE COMPARE  python reference vs mql5")
    print(f"  bars    {len(bars)}  from {bars_path.name}"
          f"{'  (header row skipped)' if had_header else ''}")
    print(f"  python  {len(py)} events")
    print(f"  mql5    {len(mq)} events  from {mql5_path.name}")
    print()

    # Align the two streams so that one missing event is reported as one
    # missing event, not as every later index being shifted.
    sm = difflib.SequenceMatcher(a=py, b=mq, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        n = max(i2 - i1, j2 - j1)
        for k in range(n):
            a = py[i1 + k] if i1 + k < i2 else None
            b = mq[j1 + k] if j1 + k < j2 else None
            diffs.append((i1 + k, a, b))

    orphans, open_at_end = sweep_accounting(py)
    if orphans:
        print(f"SWEEP ACCOUNTING: {len(orphans)} sweep(s) ended with no resolution event.")
        print("  A new sweep replaced a pending one, so the observation was discarded.")
        for t, e in orphans[:5]:
            print(f"    orphaned  {t}  {e}")
        if len(orphans) > 5:
            print(f"    ... and {len(orphans) - 5} more")
        print("  This is a property of the rule, identical in all targets, so the")
        print("  comparison below cannot see it. It is reported separately on purpose.")
        print()
    if open_at_end:
        print(f"  still open at the end of the feed: {open_at_end[0]}  {open_at_end[1]}")
        print()

    if not diffs:
        print(f"VERDICT: AGREE - python and mql5 emit the same {len(py)} events, "
              "in the same order, on the same bar times.")
        return 0

    print(f"VERDICT: DISAGREE - {len(diffs)} difference(s) in "
          f"{max(len(py), len(mq))} events.")
    first = diffs[0]
    idx, a, b = first
    print(f"  first divergence at python event #{idx}:")
    print(f"    expected (python) : {a[0]}  {a[1]}" if a else
          "    expected (python) : <nothing - mql5 has an extra event>")
    print(f"    actual   (mql5)   : {b[0]}  {b[1]}" if b else
          "    actual   (mql5)   : <missing>")
    print()
    print("  all differences:")
    for idx, a, b in diffs[:20]:
        kind = "missing in mql5" if b is None else ("extra in mql5" if a is None else "differs")
        print(f"    #{idx:<5} {kind:<16} python={a if a else '-'}  mql5={b if b else '-'}")
    if len(diffs) > 20:
        print(f"    ... and {len(diffs) - 20} more")
    print()
    print("  by type, python:", dict(Counter(e for _, e in py)))
    print("  by type, mql5  :", dict(Counter(e for _, e in mq)))
    return 1


def self_test():
    """Prove the comparison can fail: drop one event and require it to be found."""
    bars, _ = load_bars(DEF_BARS)
    ref = load_reference(DEF_REF)
    py = [(t, e) for t, e in ref.run(bars)]
    if len(py) < 10:
        die_setup("not enough events to self-test")
    cut = len(py) // 2
    mq = py[:cut] + py[cut + 1:]
    sm = difflib.SequenceMatcher(a=py, b=mq, autojunk=False)
    diffs = [op for op in sm.get_opcodes() if op[0] != "equal"]
    removed = py[cut]
    n = sum(max(i2 - i1, j2 - j1) for _, i1, i2, j1, j2 in diffs)
    print("SEANCE SELF-TEST")
    print(f"  removed one event from the mql5 side: {removed[0]}  {removed[1]}")
    print(f"  differences reported: {n}")
    if n == 1 and diffs and py[diffs[0][1]] == removed:
        print("  PASS: exactly one difference, and it names the removed event.")
        return 0
    print("  FAIL: the comparison did not isolate the removed event.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:
        # the output was piped into something that closed early, e.g. `| head`
        try:
            sys.stdout.close()
        finally:
            sys.exit(1)
