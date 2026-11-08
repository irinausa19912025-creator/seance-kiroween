# Séance — one rule, three hostile runtimes, proved equal

**Séance is one application: a rule compiler and an equivalence prover for three runtimes
that cannot execute side by side.**

A trading rule is written once, as data. Séance compiles it into a **Python reference**, an
**MQL5 expert** (the closed MetaTrader 5 environment) and a **TradingView Pine v6**
indicator (the closed TradingView environment), then runs the implementations over the same
candles and reports every disagreement, event by event, with the bar time. The three
generated files are the application's output, not three separate apps: they share no
runtime and no standard library, and there is no way to execute them side by side — only
their event streams can be compared, and Séance compares them by machine.

The point is not translation — translators already exist, and the honest ones say in their
own documentation that they cannot promise the translation behaves like the original. The
point is the report. On the example shipped here, Python and MQL5 matched on all 618 events;
Pine was checked by hand, by event counts.

Who needs this: anyone who ships the same trading rule on more than one platform. Indicator
vendors maintain an MT5 version and a TradingView version of one rule and have no way to
show a buyer that the two are the same tool; Séance turns that from a promise into a
machine-checked fact.

**Live demo:** [`docs/`](docs/) — the generators run in your browser; edit a predicate and
watch all three targets change.

## Try it in 30 seconds

```bash
python3 verify/compare.py
```

```
SEANCE COMPARE  python reference vs mql5
  bars    2000  from synthetic_bars.tsv
  python  618 events
  mql5    618 events  from synthetic_mql5_events.tsv

VERDICT: AGREE - python and mql5 emit the same 618 events, in the same order, on the same bar times.
```

No install, no network, no API key: standard-library Python 3 only.

## Try to break it

Edit any predicate in `skeletons/sweep_bos.json` — or let the acceptance suite do the
sabotage for you:

```bash
python3 verify/acceptance.py
```

It mutates every one of the 7 predicates and fails unless each mutation changes the
behaviour and the generated code of all three targets. Echoing the rule into a comment
block does not count: comments are stripped before comparing.

## What is in the box

| | |
|---|---|
| `skeletons/sweep_bos.json` | the rule, as data: parameters, pool, detections, resolutions |
| `rules/expr.py` | the predicate language — tokenizer, parser, validator |
| `rules/model.py` | skeleton loader; every malformed field is named, never a bare `KeyError` |
| `generators/emit_*.py` | three emitters: Python, MQL5, Pine v6 |
| `verify/compare.py` | ordered event-stream comparison, event by event |
| `verify/acceptance.py` | nine checks that the skeleton really drives the generated code |
| `verify/test_emit_equivalence.py` | 468 generated cases against the parsed tree |
| `demo/` | 2,000 synthetic candles, the recorded MQL5 run, and how to repeat both |

## The rule language

Deliberately small and closed: six comparisons, `and` / `or` / `not`, parentheses, integer
literals, declared parameters, and nine built-in terms (`open`, `high`, `low`, `close`,
`pool_high`, `pool_low`, `entry_high`, `entry_low`, `bars_since_entry`). Anything else — an
unknown name, a function call, a stray symbol — is refused with the offending text and its
character position. A predicate is never silently accepted as something it is not.

## How the equality is checked

Three independent harnesses, all standard library:

1. **`compare.py`** — the Python reference and the MQL5 expert over the same candles: the two
   event streams compared in order, not as summary counts. Sweeps that end without a
   resolution are reported separately, so the comparison cannot hide them.
2. **`acceptance.py`** — nine checks, run against a throwaway copy of the repository:
   regression against a recorded baseline; the sweep lifecycle; that changing a predicate
   changes the behaviour *and* all three emitted targets; that an unsupported expression is
   refused; that a whitespace-only edit changes nothing (so the predicate is parsed, not
   pasted); and that **every** predicate reaches all three targets, with comments stripped
   before comparing, so a generator cannot pass by echoing the skeleton into a comment block.
   That last check is the one that catches a rule frozen into the generator.
3. **`test_emit_equivalence.py`** — 468 cases, 37,908 evaluations, comparing the emitted code
   against the parsed expression tree.

Current state, on the data shipped here:

```
compare.py                 AGREE      618 vs 618 events, 0 discrepancies
acceptance.py              ACCEPTED   9/9 checks
test_emit_equivalence.py   PASS       468 cases, 37,908 evaluations, 0 disagreements
```

## What is proved, and what is not

**Proved.** For this rule, these parameters and these 2,000 candles, the generated Python and
MQL5 implementations emit the same events, in the same order, on the same bar times. Every
predicate in the skeleton demonstrably reaches all three generated targets.

**Recorded, not re-run on demand.** The MQL5 side. `demo/synthetic_mql5_events.tsv` is the
output of the generated expert compiled in MetaEditor (0 errors, 0 warnings) and run inside a
real MetaTrader 5 terminal over these candles. Repeating that step needs MetaTrader;
`demo/README.md` says exactly how.

**Checked by hand, once.** Pine. TradingView runs Pine only on its own platform, so the
emitted Pine was compiled there and its counters read manually; the Python reference stands in
for it in the automated run. Closing this gap — generating the instrumented probe from the
skeleton instead of editing it by hand — is specified in
[`.kiro/specs/04-probe-variant.md`](.kiro/specs/04-probe-variant.md) and is **not implemented
yet**.

**Pre-existing work.** The sweep → break-of-structure rule itself comes from the author's
published ChartZenFX indicators. Every line of code in this repository was written during
the hackathon submission period.

**Not claimed.** That any two implementations of any rule agree. That the rule is profitable —
the project measures agreement, not profit. The shipped candles are synthetic.

Earlier runs against market data (a broker feed and an exchange API) are not included: those
feeds may not be redistributed, so nothing here depends on data a reader cannot regenerate.

## Build

```bash
./build.sh skeletons/sweep_bos.json    # one skeleton -> three implementations
python3 verify/compare.py              # compare the event streams
python3 verify/acceptance.py           # nine checks on a throwaway copy
```

## Licence

MIT. See [LICENSE](LICENSE).
