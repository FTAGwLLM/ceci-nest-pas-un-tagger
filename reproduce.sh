#!/usr/bin/env bash
# Regenerate all paper figures into output/ (or $1) and check the paper numbers.
set -euo pipefail
# A user-given path is relative to the caller's directory, the default to the repository.
if [ $# -gt 0 ]; then
    mkdir -p "$1"
    OUT="$(cd "$1" && pwd)"
fi
cd "$(dirname "$0")"
OUT="${OUT:-$(pwd)/output}"
mkdir -p "$OUT"
PYTHON="${PYTHON:-python3}"

echo "== Checking data integrity"
if command -v sha256sum >/dev/null; then
    (cd data && sha256sum -c SHA256SUMS)
else
    (cd data && shasum -a 256 -c SHA256SUMS)
fi

echo "== Section 2: tagging performance (figures 1-3)"
"$PYTHON" evaluation/Section2-plots/make_performance_plots.py "$OUT"

echo "== Section 3: explainability (figures 4-5)"
"$PYTHON" evaluation/Section3-plots/make_bubble_plots.py "$OUT"
"$PYTHON" evaluation/Section3-plots/make_theme_plots.py "$OUT"

echo "Figures written to $OUT; reference versions are in evaluation/*/figures/"
