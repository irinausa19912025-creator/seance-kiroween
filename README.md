# Séance — one trading rule, three implementations, proved equal

A trading rule is written once, as data. Séance emits it as **Pine v6**, **MQL5** and a
**Python reference**, then runs two of them over the same candles and reports every
disagreement, event by event, with the bar time.

The point is not translation. Translators already exist. The point is the proof that the
copies did not drift.

## Status of the prototype

Working, on real data.

- Skeleton: `skeletons/sweep_bos.json` — liquidity sweep to break of structure.
- Emitters: `generators/emit_python.py`, `emit_mql5.py`, `emit_pine.py`.
- Harness: `verify/compare.py`.

**First run, EURUSD H4, 5000 closed candles (2023-08-15 to 2026-11-02), broker feed:**

```
эталон Python : 1098 событий
MQL5          : 1098 событий
расхождений   : 0
SWEEP_HIGH 256 · SWEEP_LOW 294 · BOS 233 · CANCEL 311 · EXPIRE 4
```

The MQL5 side is the generated expert, compiled by MetaEditor (0 errors, 0 warnings) and run
inside a real MetaTrader 5 terminal over the same TSV of bars. The comparison is of the two
event streams in order, not of summary counts.

## What is and is not proved

Proved: for this rule, these parameters and these 5000 candles, the generated Python and MQL5
implementations emit the same events in the same order.

Not proved: that any two implementations of any rule agree. The Pine output is emitted but not
yet executed automatically — TradingView does not run Pine outside its own platform, so Pine is
compiled and checked by hand once, and the Python reference stands in for it in the automated run.

No statement is made here about profitability. The project measures agreement, not profit.

## Build

```
./build.sh skeletons/sweep_bos.json
python3 verify/compare.py
```

## Licence
MIT.
