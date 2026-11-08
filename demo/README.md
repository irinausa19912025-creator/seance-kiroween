# Reproducible example on synthetic candles

Nothing here is market data. Every candle is produced by `make_bars.py` from a
fixed seed, so the TSV is byte-identical on any machine and carries no
third-party rights.

## What anyone can repeat — no MetaTrader, no network

```
python3 demo/make_bars.py demo/synthetic_bars.tsv 2000 20261104
python3 verify/compare.py
```

Expected: `AGREE - python and mql5 emit the same 618 events, in the same order,
on the same bar times.`

`synthetic_mql5_events.tsv` is the recorded output of a real MetaTrader 5 run
(see below). Re-running the comparison re-derives the Python side from scratch
and checks it against that recording; it does not re-run MetaTrader.

## What needs MetaTrader 5

Producing `synthetic_mql5_events.tsv` again. The expert reads
`MQL5\Files\Zen\seance_bars.tsv` and writes `seance_mql5_events.tsv`, so:

1. copy `demo/synthetic_bars.tsv` to the terminal's `MQL5\Files\Zen\seance_bars.tsv`
2. attach the compiled `SeanceSweepBos` expert to any chart
3. copy the written `seance_mql5_events.tsv` back here

## The run recorded here

| | |
|---|---|
| bars | 2000 synthetic H1 candles, seed 20261104 |
| expert's own report | `OK bars=2000 events=618` |
| events | 618 on both sides, 0 discrepancies |
| breakdown | SWEEP_HIGH 176 · SWEEP_LOW 133 · BOS 110 · CANCEL 197 · EXPIRE 2 |

Not an empty match: all five event types occur.

## Which binary produced it

| file | MD5 |
|---|---|
| `out/SeanceSweepBos.mq5` (repository source) | 85d470ae3b88041073703bc74d92c44e |
| `SeanceSweepBos.ex5` (compiled, MetaEditor: 0 errors, 0 warnings) | a9bc299cea4d9b32401a16502a2a6527 |
| `demo/make_bars.py` | 26e27740cd25267989a2748cd71dbc71 |
| `demo/synthetic_bars.tsv` | d8468e6d269762f405c3d5082cb91bcc |
| `demo/synthetic_mql5_events.tsv` | 401f1dec938d00881a8068476ad0485c |

The repository source and the file that was compiled are byte-identical.

## Limits

Synthetic candles prove that the generated implementations agree with each
other. They say nothing about behaviour on real market data, and nothing about
whether the rule is profitable. The Pine target is not covered by this example.
