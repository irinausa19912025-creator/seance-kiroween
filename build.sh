#!/bin/bash
# one skeleton -> three implementations
set -e
cd "$(dirname "$0")"
S=${1:-skeletons/sweep_bos.json}
python3 generators/emit_python.py "$S" out/ref_sweep_bos.py
python3 generators/emit_mql5.py   "$S" out/SeanceSweepBos.mq5
python3 generators/emit_pine.py   "$S" out/sweep_bos.pine
echo "built from $S"
