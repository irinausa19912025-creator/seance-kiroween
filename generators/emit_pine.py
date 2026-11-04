"""Emit a Pine v6 implementation from a parsed Seance skeleton.

Nothing in this module contains the rule's conditions as literal text: the
detections, the resolutions, their order, the event names, the side each one
applies to and the declared policies are all read from the skeleton, so editing
the skeleton changes the generated script.  The state machine around them is
fixed and matches the Python and MQL5 emitters: one pending observation at a
time; on each confirmed bar the pending observation is tested for resolution
before a new detection is considered; the pool is the extreme of the previous
``pool_len`` closed bars and detection only starts once that many bars exist.
"""
import os
import pathlib
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from rules.model import load
from rules import expr


# ── expression rendering ─────────────────────────────────────────────────── #

def _var_name(key: str) -> str:
    """Pine variable name for a parameter key: pool_len -> poolLen."""
    head, *rest = key.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _emit(node, vm: dict) -> str:
    """Render an expr AST node as a Pine expression.

    Every non-leaf node is parenthesised.  Pine's precedence is not the rule
    language's in every case, and an expression that reads differently after
    emission is a different rule; full parenthesisation removes the question.
    The output still depends only on the tree, so a whitespace-only edit to the
    skeleton produces byte-identical source.
    """
    if isinstance(node, expr.Lit):
        return str(node.value)
    if isinstance(node, expr.Var):
        return vm[node.name]
    if isinstance(node, expr.Cmp):
        return f"({_emit(node.left, vm)} {node.op} {_emit(node.right, vm)})"
    if isinstance(node, expr.Not):
        return f"(not {_emit(node.operand, vm)})"
    if isinstance(node, expr.And):
        return f"({_emit(node.left, vm)} and {_emit(node.right, vm)})"
    if isinstance(node, expr.Or):
        return f"({_emit(node.left, vm)} or {_emit(node.right, vm)})"
    raise TypeError(f"cannot emit AST node {node!r}")


def _varmap(skel, ctx: str) -> dict:
    """Identifier -> Pine expression, for "detection" or "resolution"."""
    vm = {"open": "open", "high": "high", "low": "low", "close": "close"}
    if ctx == "detection":
        vm["pool_high"] = "ph"
        vm["pool_low"] = "pl"
    else:
        vm["entry_high"] = "sHi"
        vm["entry_low"] = "sLo"
        vm["bars_since_entry"] = "(bar_index - sBar)"
    for key in skel.params:
        vm[key] = _var_name(key)
    return vm


_COLORS = ("color.orange", "color.blue", "color.teal", "color.gray",
           "color.purple", "color.maroon", "color.olive", "color.navy")


# ── skeleton -> source ───────────────────────────────────────────────────── #

def generate(skel, skel_filename: str) -> str:
    """Return the full Pine v6 source for a Skeleton."""
    if skel.detection_conflict != "skip_both":
        raise NotImplementedError(
            f"detection_conflict {skel.detection_conflict!r} is not supported "
            "by the Pine emitter (only 'skip_both')")
    if skel.collision_policy != "overwrite":
        raise NotImplementedError(
            f"collision_policy {skel.collision_policy!r} is not supported "
            "by the Pine emitter (only 'overwrite')")

    pool_var = _var_name(skel.pool.lookback_param)
    dvm = _varmap(skel, "detection")
    rvm = _varmap(skel, "resolution")
    sides = sorted({d.side for d in skel.detections})
    code = {side: i + 1 for i, side in enumerate(sides)}

    # one colour per distinct event name, assigned in order of appearance
    names = []
    for d in skel.detections:
        if d.event not in names:
            names.append(d.event)
    for r in skel.resolutions:
        if r.event not in names:
            names.append(r.event)
    colour = {n: _COLORS[i % len(_COLORS)] for i, n in enumerate(names)}

    L = []
    L.append(f"// generated from {skel_filename} by Seance - do not edit by hand")
    L.append(f"// skeleton: {skel.name} ({skel.id} v{skel.version})")
    L.append(f"// closed_candles_only: {str(skel.closed_candles_only).lower()}")
    L.append(f"// detection_conflict: {skel.detection_conflict}")
    L.append(f"// collision_policy: {skel.collision_policy}")
    L.append("//@version=6")
    L.append(f'indicator("{skel.name}", overlay = true, max_labels_count = 500)')
    L.append("")
    for key, p in skel.params.items():
        mn = f", minval = {p.min}" if p.min is not None else ""
        L.append(f'{_var_name(key)} = input.int({p.default}, "{p.title}"{mn})')
    L.append("")
    L.append("var int   side = 0")
    L.append("var int   sBar = 0")
    L.append("var float sHi  = na")
    L.append("var float sLo  = na")
    L.append("")
    L.append("f_mark(string txt, color col) =>")
    L.append("    label.new(bar_index, na, txt, xloc = xloc.bar_index, yloc = yloc.belowbar,")
    L.append("              style = label.style_label_up, color = col,")
    L.append("              textcolor = color.white, size = size.tiny)")
    L.append("")
    L.append(f"ph = ta.highest(high[1], {pool_var})")
    L.append(f"pl = ta.lowest(low[1],  {pool_var})")
    L.append("")
    guard = "barstate.isconfirmed" if skel.closed_candles_only else "true"
    L.append(f"if {guard}")

    # ── resolution, in skeleton order, first match wins ──────────────────── #
    L.append("    if side != 0")
    for si, side in enumerate(sides):
        applicable = [r for r in skel.resolutions
                      if r.target == side or r.target == "any"]
        kw = "if" if si == 0 else "else if"
        L.append(f"        {kw} side == {code[side]}")
        if not applicable:
            L.append("            na")
            continue
        for j, r in enumerate(applicable):
            k2 = "if" if j == 0 else "else if"
            L.append(f"            {k2} {_emit(r.when, rvm)}")
            L.append(f'                f_mark("{r.event}", color.new({colour[r.event]}, 20))')
            L.append("                side := 0")

    # ── detection, once the pool has enough closed bars ──────────────────── #
    L.append(f"    if bar_index >= {pool_var}")
    flags = []
    for i, d in enumerate(skel.detections):
        flags.append(f"_d{i}")
        L.append(f"        bool _d{i} = {_emit(d.when, dvm)}")
    count = " + ".join(f"({f} ? 1 : 0)" for f in flags) or "0"
    L.append(f"        int _n = {count}")
    L.append("        if _n == 1")
    for i, d in enumerate(skel.detections):
        kw = "if" if i == 0 else "else if"
        L.append(f"            {kw} {flags[i]}")
        L.append(f'                f_mark("{d.event}", color.new({colour[d.event]}, 20))')
        L.append(f"                side := {code[d.side]}")
        L.append("                sBar := bar_index")
        L.append("                sHi  := high")
        L.append("                sLo  := low")
    return "\n".join(L) + "\n"


def main(skel_path, out_path):
    skel = load(skel_path)
    src = generate(skel, pathlib.Path(skel_path).name)
    pathlib.Path(out_path).write_text(src)
    print("written", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
