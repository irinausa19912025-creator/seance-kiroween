#!/usr/bin/env python3
"""Independent semantic-equivalence test for the Python expression emitter.

It does not trust the emitter's own claims. For every generated AST it
compares two values:

  1. eval_expr(ast, ctx)          -- the meaning of the tree, by the interpreter
  2. eval(_emit(ast, identity))   -- the meaning of the emitted Python source

If the emitter ever drops a parenthesis that Python needs, the two disagree
and the case is reported with the tree, the source and both values.

Exit code 0 = every case agreed. 1 = at least one disagreement.
"""
import itertools, random, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rules import expr
from generators.emit_python import _emit

NAMES = ["a", "b", "c", "d"]
OPS = ["<", "<=", ">", ">=", "==", "!="]
VM = {n: n for n in NAMES}


def leaves():
    for n in NAMES:
        yield expr.Var(n, 0)
    for v in (0, 1, 2):
        yield expr.Lit(v, 0)


def cmps(depth=0):
    """All single comparisons over leaves (small, exhaustive)."""
    for op in OPS:
        for l in leaves():
            for r in leaves():
                yield expr.Cmp(op, l, r)


def build_cases():
    cases = []
    L = list(leaves())
    # 1. plain comparisons
    for op in OPS:
        cases.append(expr.Cmp(op, expr.Var("a", 0), expr.Var("b", 0)))
    # 2. THE CRITICAL FAMILY: comparison whose operands are comparisons
    for op in OPS:
        for inner_l in ("<", ">", "=="):
            for inner_r in ("<", ">", "=="):
                cases.append(expr.Cmp(op,
                    expr.Cmp(inner_l, expr.Var("a", 0), expr.Var("b", 0)),
                    expr.Cmp(inner_r, expr.Var("c", 0), expr.Var("d", 0))))
    # 3. comparison with a boolean operand
    for op in ("==", "!="):
        cases.append(expr.Cmp(op,
            expr.And(expr.Cmp(">", expr.Var("a", 0), expr.Var("b", 0)),
                     expr.Cmp(">", expr.Var("c", 0), expr.Var("d", 0))),
            expr.Var("a", 0)))
        cases.append(expr.Cmp(op,
            expr.Var("a", 0),
            expr.Or(expr.Cmp("<", expr.Var("a", 0), expr.Var("b", 0)),
                    expr.Cmp("<", expr.Var("c", 0), expr.Var("d", 0)))))
        cases.append(expr.Cmp(op,
            expr.Not(expr.Cmp(">", expr.Var("a", 0), expr.Var("b", 0))),
            expr.Var("b", 0)))
    # 4. boolean trees (regression: these already worked)
    cases.append(expr.And(expr.Or(expr.Cmp(">", expr.Var("a", 0), expr.Var("b", 0)),
                                  expr.Cmp("<", expr.Var("c", 0), expr.Var("d", 0))),
                          expr.Cmp("==", expr.Var("a", 0), expr.Var("c", 0))))
    cases.append(expr.Not(expr.And(expr.Cmp(">", expr.Var("a", 0), expr.Var("b", 0)),
                                   expr.Cmp("<", expr.Var("c", 0), expr.Var("d", 0)))))
    # 5. random deep trees
    rnd = random.Random(20261102)
    def rand(d):
        if d == 0:
            return rnd.choice(L)
        k = rnd.random()
        if k < 0.45:
            return expr.Cmp(rnd.choice(OPS), rand(d - 1), rand(d - 1))
        if k < 0.65:
            return expr.And(rand(d - 1), rand(d - 1))
        if k < 0.85:
            return expr.Or(rand(d - 1), rand(d - 1))
        return expr.Not(rand(d - 1))
    for _ in range(400):
        cases.append(rand(3))
    return cases


def contexts():
    """Value assignments that make chained comparisons differ from paired ones."""
    out = []
    for vals in itertools.product((0, 1, 2), repeat=4):
        out.append(dict(zip(NAMES, vals)))
    return out


def main():
    cases, ctxs = build_cases(), contexts()
    checked = failures = 0
    bad = []
    for node in cases:
        try:
            src = _emit(node, VM)
        except Exception as e:
            bad.append((node, "<emit raised>", str(e), None, None)); failures += 1; continue
        for ctx in ctxs:
            checked += 1
            try:
                want = expr.eval_expr(node, ctx)
            except Exception as e:
                continue
            try:
                got = eval(src, {"__builtins__": {"bool": bool}}, dict(ctx))
            except Exception as e:
                bad.append((node, src, f"<eval raised: {e}>", want, None)); failures += 1; break
            if bool(want) != bool(got):
                bad.append((node, src, ctx, want, got)); failures += 1; break
    print(f"cases: {len(cases)}   evaluations: {checked}   disagreements: {failures}")
    for node, src, ctx, want, got in bad[:8]:
        print("\n--- DISAGREEMENT ---")
        print(f"  tree     : {node}")
        print(f"  emitted  : {src}")
        print(f"  context  : {ctx}")
        print(f"  tree says: {want}    code says: {got}")
    if failures:
        print(f"\nFAIL: {failures} case(s) where emitted code means something else than the tree.")
        return 1
    print("\nPASS: emitted code agrees with the tree on every case and context.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
