# Scope of the minimal working prototype

In scope:
1. A skeleton format: one rule described once, as data (JSON).
2. Three emitters from that skeleton: Pine v6 source, MQL5 source, Python reference.
3. An equivalence harness: run the Python reference and the compiled MQL5 indicator over the
   same OHLC bars, compare the event streams, and print every disagreement with its bar time.
4. One real rule end to end: liquidity sweep -> break of structure.

Out of scope for the prototype:
- A general Pine-to-MQL5 translator.
- Running Pine itself. Pine is emitted and compiled by the author on TradingView; the Python
  reference stands in for it in the automated check, and the Pine output is checked by hand once.
- Strategy performance, profitability, optimisation. This project measures agreement, not profit.
