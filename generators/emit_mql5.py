"""Emit an MQL5 implementation from a parsed Seance skeleton.

The emitted expert reads a TSV of bars and writes the event stream, so it can be
compared with the Python reference bar for bar.

Nothing in this module contains the rule's conditions as literal text: the
detections, the resolutions, their order, the event names, the side each one
applies to and the declared policies are all read from the skeleton, so editing
the skeleton changes the generated expert.  The state machine around them is
fixed and matches the Python emitter exactly: one pending observation at a time;
on each bar the pending observation is tested for resolution before a new
detection is considered; the pool is the extreme of the previous ``pool_len``
closed bars and detection only starts once that many bars exist.
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

def _input_name(key: str) -> str:
    """MQL5 input name for a parameter key: pool_len -> InpPoolLen."""
    return "Inp" + "".join(part.capitalize() for part in key.split("_"))


def _emit(node, vm: dict) -> str:
    """Render an expr AST node as an MQL5 expression.

    Every non-leaf node is wrapped in parentheses.  C precedence differs from
    the rule language in places (``&&`` binds tighter than ``||``, a comparison
    does not chain, ``!`` binds tighter than everything), and an expression that
    reads differently after emission is a different rule.  Full parenthesisation
    removes the question entirely; the output still depends only on the tree, so
    a whitespace-only edit to the skeleton produces byte-identical source.
    """
    if isinstance(node, expr.Lit):
        return str(node.value)
    if isinstance(node, expr.Var):
        return vm[node.name]
    if isinstance(node, expr.Cmp):
        return f"({_emit(node.left, vm)} {node.op} {_emit(node.right, vm)})"
    if isinstance(node, expr.Not):
        return f"(!{_emit(node.operand, vm)})"
    if isinstance(node, expr.And):
        return f"({_emit(node.left, vm)} && {_emit(node.right, vm)})"
    if isinstance(node, expr.Or):
        return f"({_emit(node.left, vm)} || {_emit(node.right, vm)})"
    raise TypeError(f"cannot emit AST node {node!r}")


def _varmap(skel, ctx: str) -> dict:
    """Identifier -> MQL5 expression, for "detection" or "resolution"."""
    vm = {"open": "op[k]", "high": "hi[k]", "low": "lo[k]", "close": "cl[k]"}
    if ctx == "detection":
        vm["pool_high"] = "ph"
        vm["pool_low"] = "pl"
    else:
        vm["entry_high"] = "phi"
        vm["entry_low"] = "plo"
        vm["bars_since_entry"] = "(k - pbar)"
    for key in skel.params:
        vm[key] = _input_name(key)
    return vm


# ── skeleton -> source ───────────────────────────────────────────────────── #

_HEAD = r'''//+------------------------------------------------------------------+
//| generated from {skel} by Seance - do not edit by hand            |
//| skeleton: {name} ({sid} v{ver})                                  |
//| closed_candles_only: {closed}                                    |
//| detection_conflict: {dconf}   collision_policy: {cpol}           |
//| Reads Files/Zen/seance_bars.tsv, writes Files/Zen/seance_mql5_events.tsv |
//+------------------------------------------------------------------+
#property copyright "Seance"
#property version   "1.00"

'''

_READER = r'''
int OnInit()
  {
   int fin = FileOpen("Zen\\seance_bars.tsv", FILE_READ|FILE_TXT|FILE_ANSI);
   if(fin == INVALID_HANDLE)
     { FileSave("Zen\\seance_done.txt", "FAIL no bars file"); return INIT_SUCCEEDED; }

   string times[]; double op[], hi[], lo[], cl[];
   int n = 0;
   while(!FileIsEnding(fin))
     {
      string line = FileReadString(fin);
      if(StringLen(line) < 5) continue;
      string p[];
      if(StringSplit(line, '\t', p) < 5) continue;
      if(p[1] == "open") continue;                       // header
      ArrayResize(times, n+1); ArrayResize(op, n+1);
      ArrayResize(hi, n+1); ArrayResize(lo, n+1); ArrayResize(cl, n+1);
      times[n] = p[0];
      op[n] = StringToDouble(p[1]);
      hi[n] = StringToDouble(p[2]);
      lo[n] = StringToDouble(p[3]);
      cl[n] = StringToDouble(p[4]);
      n++;
     }
   FileClose(fin);

   int fout = FileOpen("Zen\\seance_mql5_events.tsv", FILE_WRITE|FILE_TXT|FILE_ANSI);
   int pside = 0, pbar = -1;
   double phi = 0, plo = 0;
   int evcount = 0;
'''

_TAIL = r'''   FileClose(fout);
   FileSave("Zen\\seance_done.txt", "OK bars=" + IntegerToString(n) + " events=" + IntegerToString(evcount));
   return INIT_SUCCEEDED;
  }

void FileSave(string fn, string txt)
  {
   int f = FileOpen(fn, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(f != INVALID_HANDLE) { FileWriteString(f, txt + "\n"); FileClose(f); }
  }

void OnTick() {}
void OnDeinit(const int r) {}
'''


def generate(skel, skel_filename: str) -> str:
    """Return the full MQL5 source for a Skeleton."""
    if skel.detection_conflict != "skip_both":
        raise NotImplementedError(
            f"detection_conflict {skel.detection_conflict!r} is not supported "
            "by the MQL5 emitter (only 'skip_both')")
    if skel.collision_policy != "overwrite":
        raise NotImplementedError(
            f"collision_policy {skel.collision_policy!r} is not supported "
            "by the MQL5 emitter (only 'overwrite')")

    pool_input = _input_name(skel.pool.lookback_param)
    dvm = _varmap(skel, "detection")
    rvm = _varmap(skel, "resolution")
    sides = sorted({d.side for d in skel.detections})
    code = {side: i + 1 for i, side in enumerate(sides)}   # "high" -> 1, "low" -> 2

    L = []
    L.append(_HEAD.format(skel=skel_filename, name=skel.name, sid=skel.id,
                          ver=skel.version, closed=str(skel.closed_candles_only).lower(),
                          dconf=skel.detection_conflict, cpol=skel.collision_policy))
    for key, p in skel.params.items():
        L.append(f'input int {_input_name(key)} = {p.default};   // {p.title}')
    L.append(_READER)

    L.append("   for(int k = 0; k < n; k++)")
    L.append("     {")

    # ── resolution, in skeleton order, first match wins ──────────────────── #
    L.append("      if(pside != 0)")
    L.append("        {")
    for si, side in enumerate(sides):
        applicable = [r for r in skel.resolutions
                      if r.target == side or r.target == "any"]
        kw = "if" if si == 0 else "else if"
        L.append(f"         {kw}(pside == {code[side]})   // {side}")
        L.append("           {")
        if not applicable:
            L.append("            // no resolution declared for this side")
        for j, r in enumerate(applicable):
            cond = _emit(r.when, rvm)
            k2 = "if" if j == 0 else "else if"
            L.append(f"            {k2}({cond})")
            L.append(f'              {{ FileWriteString(fout, times[k] + "\\t{r.event}\\n"); '
                     f"pside = 0; evcount++; }}")
        L.append("           }")
    L.append("        }")

    # ── detection, once the pool has enough closed bars ──────────────────── #
    L.append(f"      if(k >= {pool_input})")
    L.append("        {")
    L.append(f"         double ph = hi[k-{pool_input}], pl = lo[k-{pool_input}];")
    L.append(f"         for(int j = k-{pool_input}; j < k; j++)")
    L.append("           { if(hi[j] > ph) ph = hi[j]; if(lo[j] < pl) pl = lo[j]; }")
    flags = []
    for i, d in enumerate(skel.detections):
        flags.append(f"_d{i}")
        L.append(f"         bool _d{i} = {_emit(d.when, dvm)};   // {d.event}")
    count = " + ".join(f"({f} ? 1 : 0)" for f in flags) or "0"
    L.append(f"         int _n = {count};")
    L.append("         if(_n == 1)")
    L.append("           {")
    for i, d in enumerate(skel.detections):
        kw = "if" if i == 0 else "else if"
        L.append(f"            {kw}({flags[i]})")
        L.append(f'              {{ FileWriteString(fout, times[k] + "\\t{d.event}\\n"); '
                 f"pside = {code[d.side]}; pbar = k; phi = hi[k]; plo = lo[k]; evcount++; }}")
    L.append("           }")
    L.append("        }")
    L.append("     }")
    L.append(_TAIL)
    return "\n".join(L)


def main(skel_path, out_path):
    skel = load(skel_path)
    src = generate(skel, pathlib.Path(skel_path).name)
    pathlib.Path(out_path).write_text(src)
    print("written", out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
