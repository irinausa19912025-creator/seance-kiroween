"""Emit a Pine v6 implementation from a skeleton."""
import json, sys, pathlib
TPL = '''// generated from {skel} by Seance - do not edit by hand
//@version=6
indicator("{title}", overlay = true, max_labels_count = 500)

poolLen = input.int({pool_len}, "Pool length (candles)", minval = 5)
winLen  = input.int({window}, "Setup window (candles after sweep)", minval = 1)

var int    side = 0
var int    sBar = 0
var float  sHi  = na
var float  sLo  = na

f_mark(string txt, color col) =>
    label.new(bar_index, na, txt, xloc = xloc.bar_index, yloc = yloc.belowbar,
              style = label.style_label_up, color = col, textcolor = color.white, size = size.tiny)

ph = ta.highest(high[1], poolLen)
pl = ta.lowest(low[1],  poolLen)

if barstate.isconfirmed
    if side != 0
        bool cancel = side == 1 ? high > sHi : low < sLo
        bool bos    = side == 1 ? close < sLo : close > sHi
        bool expire = bar_index - sBar >= winLen
        if cancel
            f_mark("CANCEL", color.new(color.gray, 20)), side := 0
        else if bos
            f_mark("BOS", color.new(color.teal, 20)), side := 0
        else if expire
            f_mark("EXPIRE", color.new(color.gray, 50)), side := 0
    bool sweepHigh = high > ph and close <= ph
    bool sweepLow  = low  < pl and close >= pl
    if sweepHigh and not sweepLow
        f_mark("SWEEP HIGH", color.new(color.orange, 20))
        side := 1, sBar := bar_index, sHi := high, sLo := low
    else if sweepLow and not sweepHigh
        f_mark("SWEEP LOW", color.new(color.blue, 20))
        side := 2, sBar := bar_index, sHi := high, sLo := low
'''
def main(sp, op):
    s = json.loads(pathlib.Path(sp).read_text())
    d = {p["key"]: p["default"] for p in s["params"]}
    pathlib.Path(op).write_text(TPL.format(skel=pathlib.Path(sp).name, title=s["name"],
                                           pool_len=d["pool_len"], window=d["window_len"]))
    print("written", op)
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
