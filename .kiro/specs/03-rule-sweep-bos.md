# Rule: liquidity sweep -> break of structure

Stated once, in words, and encoded in skeletons/sweep_bos.json.

- Pool: the highest high and the lowest low of the previous N closed candles.
- High sweep: the candle's high is above the pool high AND its close is back at or below it.
- Low sweep: the candle's low is below the pool low AND its close is back at or above it.
- A candle that sweeps both sides is skipped.
- A pending sweep is cancelled if a later candle exceeds the sweep candle's extreme.
- Break of structure: a later candle closes beyond the opposite end of the sweep candle.
- A pending sweep expires after L candles.
- Only closed candles are used. No lookahead.

Events emitted, in order, each with the bar time:
SWEEP_HIGH, SWEEP_LOW, CANCEL, BOS, EXPIRE.
