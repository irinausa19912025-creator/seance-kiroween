# Problem

A trading rule is written once, in words, and then re-implemented by hand on every platform:
Pine Script for TradingView, MQL5 for MetaTrader, Python for research. The three copies drift.
A sweep that counts on one platform does not count on another, and the author finds out from a
customer, not from a test.

There is no tool that takes one rule and proves that two generated implementations agree
bar for bar on the same data.

# What exists

- PineTS: runs Pine-like code in TypeScript. Does not emit MQL5. AGPL.
- CodingFleet and similar LLM converters: translate code, do not check equivalence.
- wickra-strategy-ci: CI for strategies, does not cover Pine or MQL5.

None of them answer the question this project answers: *are these two implementations the same?*
