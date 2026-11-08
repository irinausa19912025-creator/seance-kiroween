# Verification results

Everything below runs on data that ships with this repository. No network, no API key,
no market data.

## 1. Python reference vs generated MQL5 — `RUN_compare.txt`

| | |
|---|---|
| data | `demo/synthetic_bars.tsv` — 2,000 H1 candles from `demo/make_bars.py`, seed 20261104 |
| Python reference | 618 events |
| generated MQL5 expert | 618 events |
| **discrepancies** | **0** |

Breakdown: SWEEP_HIGH 176 · SWEEP_LOW 133 · BOS 110 · CANCEL 197 · EXPIRE 2.

The MQL5 side is `out/SeanceSweepBos.mq5`, compiled by MetaEditor (0 errors, 0 warnings) and
run inside a real MetaTrader 5 terminal over the same candles; the expert reported
`OK bars=2000 events=618` itself. Its event stream is recorded in
`demo/synthetic_mql5_events.tsv`. The comparison is of the two streams in order, not of
summary counts.

| artefact | MD5 |
|---|---|
| `out/SeanceSweepBos.mq5` | 85d470ae3b88041073703bc74d92c44e |
| compiled `SeanceSweepBos.ex5` | a9bc299cea4d9b32401a16502a2a6527 |
| `demo/synthetic_bars.tsv` | d8468e6d269762f405c3d5082cb91bcc |
| `demo/synthetic_mql5_events.tsv` | 401f1dec938d00881a8068476ad0485c |

## 2. The skeleton drives the code — `RUN_acceptance.txt`

Nine checks on a throwaway copy: **ACCEPTED 9/9**. The strongest of them is F — every one of
the seven predicates is mutated in turn and must change the generated Python, MQL5 and Pine,
with comments stripped before comparing.

## 3. The harness can fail — `SABOTAGE_RUN.txt`

A deliberately sabotaged copy (five predicates frozen into the loader; the skeleton echoed
into comment headers) scores **REJECTED 7/9** and names the five dead predicates. A passing
result means something only because this failing one exists.

## 4. Emitted code vs the parsed tree — `RUN_equivalence.txt`

468 generated cases, 37,908 evaluations, 0 disagreements.

## Pine

Not covered automatically. TradingView runs Pine only on its own platform, so the emitted
Pine was compiled there and its event counters read by hand against the Python reference over
an identical window; the counts matched. The probe used for that reading
(`verify/pine_probe.pine`) is **hand-edited**, which is the gap `.kiro/specs/04-probe-variant.md`
is written to close. Until it is closed, treat the Pine agreement as checked once, manually,
not as continuously proved.

## Market data

Earlier runs on a broker feed and on exchange candles are not reproduced here: those feeds may
not be redistributed. Nothing in this repository depends on data a reader cannot regenerate.
