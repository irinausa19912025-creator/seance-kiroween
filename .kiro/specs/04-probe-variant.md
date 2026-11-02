# Spec: generated probe variants and cross-target count verification

## Problem this addresses

`verify/pine_probe.pine` was written by hand: a human copied the generated
`out/sweep_bos.pine` and added event counters and a results table on top of it.
Nothing in the tool keeps that probe in sync with the generated code. If the
skeleton changes and the emitters are re-run, the hand-edited probe keeps the old
logic and the Pine comparison silently becomes meaningless.

## Goal

Every emitter must be able to produce two variants of its target from one
skeleton:

- **plain** — exactly what is generated today.
- **probe** — the same event logic, plus windowed counters: a count for each
  event type that falls inside a time window, the number of bars counted in that
  window, and the time of the first and last counted bar.

The probe is generated from the skeleton, never copied from the plain output,
so the two cannot drift apart. A new verifier compares the probe counts of any
two targets over the same window and reports agreement or the exact per-event
differences.

## What does not change

- `skeletons/sweep_bos.json` is untouched (same rule, same params, same events).
- No second rule, no new trading logic. The probe adds counting only; it never
  changes which event fires on which bar.
- The existing `verify/compare.py` (ordered event-stream comparison of Python
  vs MQL5) stays as-is — it is the stronger, order-sensitive check.
- Recorded market data under `out/*.tsv` is not modified or deleted.
- The project stays dependency-free: standard Python 3 only.

## Design

### Single-sourcing the event logic (no drift)

Each emitter guarantees that the event-detection logic is authored once and
shared by both variants. The mechanism is chosen per target because the
languages differ, but the guarantee is the same in every case:

- **Python.** The probe imports the plain reference module and calls its
  `run()`. The event logic lives in exactly one place (the plain reference);
  the probe only adds a counting layer over the returned event list. By
  construction the probe runs the identical code object, so it cannot drift.

- **Pine and MQL5.** Each emitter authors a single template that contains the
  full event logic plus probe-only instrumentation. Probe-only lines are marked
  with a trailing ` //~p` comment; inline probe-only tokens are wrapped in
  `/*P*/ ... /*P*/` span markers (MQL5 only, where single-line blocks must stay
  intact). The plain variant is produced by removing every marked line and
  span; the probe variant is produced by stripping the markers and keeping the
  content. The event-logic lines are unmarked, so they are byte-identical
  between the two variants. Changing event logic changes a shared line and
  affects both outputs; changing a counter touches only a marked line and never
  the plain output. The two cannot drift.

  Pine has no block comments, so Pine uses line markers only — and every
  probe-only addition in Pine is a whole line, so line markers suffice.

### What the probe reports

Each probe emits a **counts file**: a small tab-separated key/value document
that any two targets can produce in the same shape, so one target-agnostic
verifier can compare them. Times are epoch milliseconds (canonical, no
per-platform formatting differences). Fields, in order:

```
target	<python|mql5|pine>
window_start	<ms>
window_end	<ms>
bars_counted	<int>
first_bar	<ms>
last_bar	<ms>
SWEEP_HIGH	<int>
SWEEP_LOW	<int>
BOS	<int>
CANCEL	<int>
EXPIRE	<int>
total	<int>
```

Event names come from the skeleton `events` list, so the format is generated,
not hardcoded beyond the skeleton.

### Per-target probe behavior

- **Python probe** (`out/ref_sweep_bos_probe.py`): a runnable script.
  `python3 out/ref_sweep_bos_probe.py <bars.tsv> <start> <end> [counts_out]`.
  Loads bars (accepts ms-integer or `YYYY.MM.DD HH:MM` / `YYYY-MM-DD HH:MM`
  times, normalised to ms), calls the imported plain `run()`, filters events to
  the window, counts per type, counts bars in the window, records first/last
  bar, and writes the counts file (to `counts_out` or stdout). The window bounds
  are accepted as ms integers or datetime strings.

- **MQL5 probe** (`out/SeanceSweepBos_probe.mq5`): an expert that reads the same
  bars TSV as the plain expert, runs the same loop, writes the event stream
  (identical to the plain output) **and** writes `seance_mql5_counts.tsv` with
  the windowed counts. Window bounds come from two string inputs
  (`InpStart`, `InpEnd`, `YYYY.MM.DD HH:MM`); bar times are compared
  lexicographically (valid for that fixed-width format) and converted to ms for
  the counts file. The probe is a strict superset of the plain expert.

- **Pine probe** (`out/sweep_bos_probe.pine`): an indicator that runs the same
  event logic and renders a table with the per-event counts, `bars_counted`,
  `first_bar`/`last_bar`/`window_start`/`window_end` as ms, and `total`. Pine
  cannot write files, so the values are transcribed by hand into a counts file.
  The table shows ms (from Pine's `time`) so transcription is unambiguous.

### The verifier (`verify/probe_compare.py`)

`python3 verify/probe_compare.py <counts_a> <counts_b>`.

Parses two counts files. Compares the window/bars metadata
(`window_start`, `window_end`, `bars_counted`, `first_bar`, `last_bar`) and every
event count plus `total`, printing each field as a match or a per-field
difference with the signed delta. Verdict:

- **AGREE** (exit 0) — window, bars and all event counts match.
- **DISAGREE** (exit 1) — lists every differing field.

A window/bars mismatch means the two probes did not run over the same bars; that
is reported as a field difference (and usually a setup error, not a logic
error). The verifier is target-agnostic: it only reads two counts files.

### build.sh and README

`build.sh` emits all six artifacts (plain + probe for each of the three targets).
Each emitter takes the variant as a third argument (`plain`, default; or `probe`)
and stays backward-compatible with the old two-argument form.

`README.md` documents the two variants, the counts file, how to run the Python
probe, how to transcribe the Pine table, and how to run `probe_compare.py`. The
"what is and is not proved" section is updated: the Pine comparison is no longer
hand-edited; the probe is generated.

`verify/RESULTS.md` reproduction steps for run 2 are updated to the generated
probe + verifier flow. The hand-edited `verify/pine_probe.pine` is marked
superseded (kept for reference, not deleted).

## Verification of the work

- `./build.sh skeletons/sweep_bos.json` regenerates all six files; the three
  plain outputs are byte-identical to the previous generated outputs (the
  emitters only add marked lines/spans that are stripped for plain).
- `python3 out/ref_sweep_bos_probe.py out/coinbase_btcusd_1h.tsv "2026-09-01 00:00" "2026-11-02 05:00"`
  reproduces the RESULTS.md run-2 counts (94/65/63/93/3, 1494 bars).
- `probe_compare.py` of the Python counts vs a counts file carrying the same
  numbers reports AGREE; perturbing one count reports the exact per-event diff
  and exits 1.
- The generated Pine and MQL5 probes are inspected for syntactic validity (no
  TradingView/MetaEditor available in this environment, so compilation is stated
  as not re-verified).
