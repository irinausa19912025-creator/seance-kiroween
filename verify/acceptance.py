#!/usr/bin/env python3
"""Acceptance test for the claim that the skeleton drives the generated code.

Four checks, run against a throwaway copy of the repository so nothing here
can modify the project:

  A  REGRESSION   the unchanged skeleton reproduces the recorded baseline
                  event stream exactly.
  B  RULE DRIVES  changing one predicate in the skeleton changes the BEHAVIOUR
     CODE         of the Python implementation and changes the emitted
                  condition in all three targets.
  C  REJECTION    an expression outside the supported vocabulary is refused
                  with an error naming it, not silently ignored.
  D  PARSED NOT   a whitespace-only edit to a predicate produces byte-identical
     PASTED       output, proving the expression is parsed rather than copied.
  F  NO DEAD      EVERY predicate in the skeleton - not just the first one -
     TEXT         changes the generated code of all three targets.  Comments are
                  stripped before comparing, so a generator cannot pass by
                  echoing the skeleton into a comment block.  This is the check
                  that catches a rule frozen into the generator.

Exit code 0 only if all four pass. Standard library only.
"""
import sys, os, json, shutil, subprocess, tempfile, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "verify" / "baseline_sweep_bos_events.tsv"
BARS = ROOT / "out" / "seance_bars.tsv"
SKEL = "skeletons/sweep_bos.json"

# tokens that mark a JSON string as a rule expression rather than prose
EXPR_HINTS = ("pool_high", "pool_low", "high", "low", "close")
OPS = ("<", ">", "<=", ">=", "==", "!=")


POLICY_KEY_HINTS = ("collision", "on_new", "on_detect", "pending", "replace", "conflict")
SWEEP_PREFIXES = ("SWEEP", "DETECT")
RESOLUTION_NAMES = ("BOS", "CANCEL", "EXPIRE", "REPLACED", "TIMEOUT")


def declared_policy(skel):
    """Find a declared collision policy anywhere in the skeleton."""
    found = []

    def walk(o, path=()):
        if isinstance(o, dict):
            for k, v in o.items():
                if any(h in k.lower() for h in POLICY_KEY_HINTS) and isinstance(v, (str, bool)):
                    found.append((".".join(map(str, path + (k,))), v))
                walk(v, path + (k,))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + (i,))
    walk(skel)
    return found


def lifecycle(events):
    """Classify every detection: resolved, replaced (no resolution), or open."""
    resolved = replaced = 0
    orphan_times = []
    pending = None
    for t, e in events:
        if any(e.startswith(p) for p in SWEEP_PREFIXES):
            if pending is not None:
                replaced += 1
                orphan_times.append(pending[0])
            pending = (t, e)
        elif e in RESOLUTION_NAMES:
            if pending is not None:
                resolved += 1
                pending = None
    open_at_end = 1 if pending is not None else 0
    return resolved, replaced, open_at_end, orphan_times


results = []


def say(ok, name, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")


def find_predicates(obj, path=()):
    """Yield (json_path, value) for every string that looks like an expression."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from find_predicates(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from find_predicates(v, path + (i,))
    elif isinstance(obj, str):
        if any(op in obj for op in OPS) and any(h in obj for h in EXPR_HINTS):
            yield path, obj


def find_all_whens(obj, path=()):
    """Every predicate, located by its key, not guessed from its text.

    find_predicates() above looks for expression-shaped strings and misses
    predicates built only from parameters (bars_since_entry >= window_len has
    no price token in it).  Check F must not miss any, so it goes by the key.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "when" and isinstance(v, str) and v.strip():
                yield path + (k,), v
            else:
                yield from find_all_whens(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from find_all_whens(v, path + (i,))


def code_only(name, text):
    """The generated file with comments and blank lines removed.

    Without this, a generator that writes the skeleton into a header comment
    would make every target look like it changed while the logic stayed frozen.
    """
    marker = "#" if name.endswith(".py") else "//"
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(marker):
            continue
        if marker in s:
            s = s.split(marker, 1)[0].rstrip()
            if not s:
                continue
        out.append(s)
    return "\n".join(out)


def get_at(obj, path):
    for p in path:
        obj = obj[p]
    return obj


def set_at(obj, path, value):
    for p in path[:-1]:
        obj = obj[p]
    obj[path[-1]] = value


def build(work):
    """Run the project's own build. Returns (returncode, combined output)."""
    sh = work / "build.sh"
    if sh.exists():
        r = subprocess.run(["bash", str(sh), SKEL], cwd=work,
                           capture_output=True, text=True)
    else:
        r = subprocess.run([sys.executable, "-c", "print('no build.sh')"],
                           cwd=work, capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_reference(work):
    """Run the generated Python reference over the bars; return the event list."""
    ref = next(work.glob("out/ref_*.py"), None)
    if ref is None:
        return None, "no generated Python reference found in out/"
    code = (
        "import importlib.util,sys\n"
        f"spec=importlib.util.spec_from_file_location('r',r'{ref}')\n"
        "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "bars=[]\n"
        f"for i,l in enumerate(open(r'{BARS}')):\n"
        "    f=l.rstrip(chr(10)).split(chr(9))\n"
        "    if len(f)<5 or f[1]=='open': continue\n"
        "    bars.append((f[0],float(f[1]),float(f[2]),float(f[3]),float(f[4])))\n"
        "for t,e in m.run(bars): print(t+chr(9)+e)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=work,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr[-600:]
    return [tuple(l.split("\t")) for l in r.stdout.splitlines() if l.strip()], ""


def generated_files(work):
    return sorted(p for p in (work / "out").glob("*")
                  if p.suffix in (".py", ".mq5", ".pine"))


def snapshot(work):
    return {p.name: p.read_text() for p in generated_files(work)}


def fresh_copy(tmp, tag):
    w = pathlib.Path(tmp) / tag
    shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc"))
    return w


def main():
    print("SEANCE ACCEPTANCE TEST")
    print(f"  repository: {ROOT}")
    if not BASELINE.exists():
        print(f"  [SETUP] baseline not found: {BASELINE}")
        return 2
    baseline = [tuple(l.split("\t")) for l in BASELINE.read_text().splitlines()
                if l.strip() and not l.startswith("#")]
    print(f"  baseline:   {len(baseline)} events")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        # ---------- A. regression ----------
        print("A  REGRESSION - unchanged skeleton reproduces the baseline")
        w = fresh_copy(tmp, "a")
        rc, out = build(w)
        if rc != 0:
            say(False, "build.sh succeeds on the unchanged skeleton", out[-500:])
            return finish()
        ev, err = run_reference(w)
        if ev is None:
            say(False, "the generated reference runs", err)
            return finish()
        _, _, _, base_orphans = lifecycle(baseline)
        if ev == baseline:
            say(True, f"event stream identical to the baseline ({len(ev)} events)",
                f"the old collision policy is preserved; {len(base_orphans)} "
                "detection(s) still end with no resolution")
        else:
            # A change is allowed ONLY if it consists of resolution events added
            # for detections that previously vanished. Anything else is a regression.
            extra = [x for x in ev if x not in baseline]
            lost = [x for x in baseline if x not in ev]
            fixes = [x for x in extra
                     if x[1] in RESOLUTION_NAMES and
                     any(ot <= x[0] for ot in base_orphans)]
            ok = (not lost) and extra and len(fixes) == len(extra)
            say(ok, "any change to the baseline is the sweep-accounting fix only",
                f"baseline {len(baseline)} events, rebuilt {len(ev)} events\n"
                f"added {len(extra)} ({len(fixes)} of them resolutions for "
                f"previously orphaned detections), removed {len(lost)}\n"
                + ("" if ok else "a change that is not the accounting fix is a regression"))
        base_files = snapshot(w)

        # ---------- E. every detection has an explainable fate ----------
        print()
        print("E  SWEEP LIFECYCLE - every detection is resolved, replaced by a")
        print("   declared policy, or open at the end of the feed")
        res, rep, opn, orph = lifecycle(ev)
        total = res + rep + opn
        print(f"   resolved {res}   replaced {rep}   open at end {opn}   total detections {total}")
        skel_now = json.loads((w / SKEL).read_text())
        pol = declared_policy(skel_now)
        if rep == 0:
            say(True, "no detection is discarded without a resolution")
        elif pol:
            say(True, "replacement happens under a policy declared in the skeleton",
                "\n".join(f"{k} = {v}" for k, v in pol[:4]) +
                f"\nfirst discarded detection: {orph[0] if orph else '-'}")
        else:
            say(False, "replacement happens under a declared policy",
                f"{rep} detection(s) vanish with no resolution and the skeleton\n"
                "declares no collision policy - the fate is an accident, not a decision\n"
                f"first discarded detection: {orph[0] if orph else '-'}")

        # locate a predicate to mutate
        skel = json.loads((w / SKEL).read_text())
        preds = list(find_predicates(skel))
        if not preds:
            print()
            print("B  RULE DRIVES CODE")
            say(False, "a rule expression can be located in the skeleton",
                "no JSON string in the skeleton looks like an expression.\n"
                "Either the rule still lives in the emitters, or the new format\n"
                "stores it somewhere this test cannot recognise.")
            return finish()
        path, expr = preds[0]
        dotted = ".".join(str(p) for p in path)

        # ---------- B. rule drives code ----------
        print()
        print("B  RULE DRIVES CODE - changing one predicate changes all three targets")
        print(f"   mutating {dotted}")
        print(f"     from: {expr}")
        mutated = flip_one_operator(expr)
        print(f"       to: {mutated}")
        w = fresh_copy(tmp, "b")
        sk = json.loads((w / SKEL).read_text())
        set_at(sk, path, mutated)
        (w / SKEL).write_text(json.dumps(sk, indent=2))
        rc, out = build(w)
        if rc != 0:
            say(False, "build.sh accepts the mutated predicate", out[-400:])
        else:
            ev2, err = run_reference(w)
            if ev2 is None:
                say(False, "the mutated reference runs", err)
            elif ev2 == baseline:
                say(False, "the Python BEHAVIOUR changed",
                    "the mutated rule produced the identical event stream -\n"
                    "the predicate did not reach the generated code")
            else:
                say(True, "the Python behaviour changed",
                    f"baseline {len(baseline)} events, mutated {len(ev2)} events")
            now = snapshot(w)
            for name, text in base_files.items():
                changed = now.get(name) != text
                say(changed, f"the emitted {name} changed",
                    "" if changed else "this target still carries the old condition")

        # ---------- C. unsupported expression rejected ----------
        print()
        print("C  REJECTION - an unsupported expression is refused, not ignored")
        w = fresh_copy(tmp, "c")
        sk = json.loads((w / SKEL).read_text())
        set_at(sk, path, "frobnicate(high) ~~> moon_phase")
        (w / SKEL).write_text(json.dumps(sk, indent=2))
        rc, out = build(w)
        if rc == 0:
            say(False, "build.sh fails on an unsupported expression",
                "it exited 0 - the unsupported construct was ignored")
        else:
            # The rejection must point at the offending thing, by token or by
            # position. Accept either: naming the symbol, or naming its place.
            offending = any(x in out for x in ("frobnicate", "~~>", "moon_phase", "'~'"))
            located = "position" in out.lower() or "column" in out.lower()
            named = offending or located
            say(named, "the error points at the offending token or its position",
                out.strip().splitlines()[-1][:170] if out.strip() else "no output")

        # ---------- D. parsed not pasted ----------
        print()
        print("D  PARSED NOT PASTED - a whitespace-only edit changes nothing")
        w = fresh_copy(tmp, "d")
        sk = json.loads((w / SKEL).read_text())
        spaced = re.sub(r"\s+", "  ", expr).strip()
        if spaced == expr:
            spaced = expr.replace(" ", "   ")
        set_at(sk, path, spaced)
        (w / SKEL).write_text(json.dumps(sk, indent=2))
        rc, out = build(w)
        if rc != 0:
            say(False, "build.sh accepts a reformatted predicate", out[-300:])
        else:
            now = snapshot(w)
            same = all(now.get(n) == t for n, t in base_files.items())
            say(same, "output byte-identical after reformatting",
                "" if same else "the expression is being copied as text, not parsed")

        # ---------- F. no dead text ----------
        print()
        print("F  NO DEAD TEXT - every predicate reaches all three targets")
        all_preds = list(find_all_whens(skel))
        print(f"   {len(all_preds)} predicate(s) declared in the skeleton")
        base_code = {n: code_only(n, t) for n, t in base_files.items()}
        dead = []
        for idx, (ppath, pexpr) in enumerate(all_preds):
            pdot = ".".join(str(x) for x in ppath)
            pmut = flip_one_operator(pexpr)
            if pmut == pexpr:
                dead.append((pdot, "no operator to flip - cannot be tested", []))
                print(f"   {pdot:26s} SKIPPED - nothing to mutate")
                continue
            w2 = fresh_copy(tmp, f"f{idx}")
            sk2 = json.loads((w2 / SKEL).read_text())
            set_at(sk2, ppath, pmut)
            (w2 / SKEL).write_text(json.dumps(sk2, indent=2))
            rc2, out2 = build(w2)
            if rc2 != 0:
                dead.append((pdot, "build.sh failed on the mutation", []))
                print(f"   {pdot:26s} BUILD FAILED")
                continue
            now2 = {n: code_only(n, t) for n, t in snapshot(w2).items()}
            frozen = sorted(n for n in base_code if now2.get(n) == base_code[n])
            if frozen:
                dead.append((pdot, "ignored by", frozen))
            print(f"   {pdot:26s} {pexpr}  ->  {pmut}")
            print(f"   {'':26s} {'reaches all three targets' if not frozen else 'DEAD TEXT for: ' + ', '.join(frozen)}")
        if dead:
            detail = "\n".join(
                f"  {d}: {why}" + ((" " + ", ".join(tg)) if tg else "")
                for d, why, tg in dead)
            say(False, "every predicate changes the generated code",
                "these predicates are dead text - the generated code does not\n"
                "depend on them, so for that part the rule lives in the generator,\n"
                "not in the skeleton:\n" + detail)
        else:
            say(True, f"all {len(all_preds)} predicates change the generated code",
                "comments are stripped before comparing, so echoing the skeleton\n"
                "into a comment block does not count as reaching the code")

    return finish()


def flip_one_operator(expr):
    """Turn one comparison into its opposite, so behaviour must change."""
    for a, b in ((">=", "<"), ("<=", ">"), (">", "<="), ("<", ">=")):
        if a in expr:
            return expr.replace(a, b, 1)
    return expr + " and close > 0"


def finish():
    print()
    passed, total = sum(1 for r in results if r), len(results)
    if all(results) and results:
        print(f"VERDICT: ACCEPTED - {passed}/{total} checks passed. "
              "The skeleton drives the generated code.")
        return 0
    print(f"VERDICT: REJECTED - {passed}/{total} checks passed.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(1)
