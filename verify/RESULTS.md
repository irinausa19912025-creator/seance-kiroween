# Seance - cross-platform verification results

Three implementations are generated from one rule description
(`skeletons/sweep_bos.json`). These are the runs that compare them.

## Run 1 - Python reference vs generated MQL5

| | |
|---|---|
| Data | EURUSD H4, IC Markets Global, 5000 closed candles |
| Range | 2023-08-15 .. 2026-11-02 |
| Python reference | 1098 events |
| Generated MQL5 expert | 1098 events |
| **Discrepancies** | **0** |

Breakdown: SWEEP_HIGH 256 · SWEEP_LOW 294 · BOS 233 · CANCEL 311 · EXPIRE 4.

## Run 2 - Python reference vs generated Pine Script v6

Pine cannot export an event list, so the comparison uses counters over an
identical time window. The feed had to be identical on both sides, which
rules out a broker symbol: COINBASE BTCUSD is available both on TradingView
and from the Coinbase public candles API.

| | |
|---|---|
| Data | COINBASE BTCUSD, 1H |
| Window | 2026-09-01 00:00 .. 2026-11-02 05:00 UTC |
| Bars in window | 1494 on both sides |

| Event | Python reference | Pine in TradingView |
|---|---|---|
| SWEEP_HIGH | 94 | 94 |
| SWEEP_LOW | 65 | 65 |
| BOS | 63 | 63 |
| CANCEL | 93 | 93 |
| EXPIRE | 3 | 3 |
| **TOTAL** | **318** | **318** |

**Discrepancies: 0.** First and last counted bar matched exactly
(2026-09-01 00:00 and 2026-11-02 05:00 UTC).

The generated Pine v6 compiled in TradingView without errors on first run.

## How to reproduce run 2

1. `verify/pine_probe.pine` is the generated `out/sweep_bos.pine` with event
   counters added; nothing in the event logic differs (15 logic lines compared
   line by line, identical). Paste it into the TradingView Pine Editor,
   set the symbol to COINBASE:BTCUSD and the interval to 1H, add it to the
   chart and read the table.
2. `python3 verify/compare_pine.py out/ref_sweep_bos.py out/coinbase_btcusd_1h.tsv "2026-09-01 00:00" "2026-11-02 05:00"`

`out/coinbase_btcusd_1h.tsv` holds 1800 candles (2026-08-19 07:00 ..
2026-11-02 06:00 UTC, no gaps) downloaded from the Coinbase public API;
the extra 306 candles before the window are warm-up for the 20-candle pool.

## What these runs prove, and what they do not

Proved: three implementations generated from one description produce the same
events on the same candles - 1098 for Python/MQL5, 318 for Python/Pine.
The identical Pine result over 1494 bars also means TradingView's COINBASE
BTCUSD 1H candles and the Coinbase API candles agree over that window.

Not proved: that the trading rule itself is correct or profitable. Agreement
between implementations is a consistency check, not a quality check. Nor is
anything proved about other symbols, timeframes or brokers.
