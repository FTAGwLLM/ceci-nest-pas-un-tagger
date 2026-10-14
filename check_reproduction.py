"""Check that the numbers quoted in the paper are reproduced from data/.

Exit code 0 if all AUCs and Pearson correlations agree within 1e-3.
"""
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "evaluation" / "Section2-plots"))
import make_performance_plots as perf  # noqa: E402

TOLERANCE = 1e-3
PAPER_AUC = {  # (background, tagger): value
    ("light", "GN2"): 0.971, ("light", "DL1"): 0.963, ("light", "Claude"): 0.928,
    ("c", "GN2"): 0.913, ("c", "DL1"): 0.897, ("c", "Claude"): 0.815,
}
PAPER_R = {("DL1", "GN2"): 0.964, ("Claude", "DL1"): 0.880, ("Claude", "GN2"): 0.870}
BACKGROUND = {"light": "ujets", "c": "cjets"}

with h5py.File(perf.JETS_PATH, "r") as f:
    jets = f["jets"][:]
truth = np.array([perf.TRUTH[i] for i in jets[perf.TRUTH_VAR]])
d_b = {t: perf.discriminant_b(jets, t) for t in perf.TAGGERS}

failed = False
for (bkg, tagger), expected in PAPER_AUC.items():
    *_, auc = perf.roc_auc(d_b[tagger][truth == "bjets"], d_b[tagger][truth == BACKGROUND[bkg]])
    ok = abs(auc - expected) < TOLERANCE
    failed |= not ok
    print(f"{'OK  ' if ok else 'FAIL'} AUC b vs {bkg:5s} {tagger:6s} {auc:.4f}  paper {expected:.3f}")
for (a, b), expected in PAPER_R.items():
    r = np.corrcoef(d_b[a], d_b[b])[0, 1]
    ok = abs(r - expected) < TOLERANCE
    failed |= not ok
    print(f"{'OK  ' if ok else 'FAIL'} r D_b {a + '-' + b:16s} {r:.4f}  paper {expected:.3f}")

print("\nReproduction FAILED" if failed else "\nAll paper numbers reproduced")
sys.exit(int(failed))
