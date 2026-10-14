#!/usr/bin/env python3
"""Merge the model predictions back with truth labels and reference taggers.

Takes the rows [jet-start, jet-start + N) of the original JetSet file, with all
their `jets` and `tracks` fields (truth, GN2, DL1, ...), and appends the four
Claude probabilities from predictions.csv. Row i of the CSV is jet i of the
reco-only input, i.e. original row jet-start + i.

Paper output:
    python attach_labels.py --predictions ../data/predictions.csv \
        --original mc-flavtag-ttbar-medium.h5 \
        --output ../data/mc-flavtag-ttbar-medium_w_Opus.h5 --jet-start 100000
"""
import argparse
import os
import sys

import h5py
import numpy as np
import pandas as pd

PROBS = ["Claude_pb", "Claude_pc", "Claude_pu", "Claude_ptau"]
DATASETS = ["jets", "tracks"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--original", required=True, help="JetSet file (mc-flavtag-ttbar-medium.h5)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--jet-start", type=int, default=100_000,
                    help="original row of the first jet (same as strip_labels.py)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if os.path.exists(args.output) and not args.overwrite:
        sys.exit(f"{args.output} exists, use --overwrite")

    pred = pd.read_csv(args.predictions)
    n = len(pred)
    if not (pred["jet_index"].to_numpy() == np.arange(n)).all():
        sys.exit("jet_index is not 0..N-1: predictions are not in input order")
    p = pred[PROBS].to_numpy(np.float64)
    if np.isnan(p).any():
        sys.exit("missing probabilities")
    if (p < 0).any() or (p > 1).any():
        sys.exit("probabilities outside [0, 1]")
    dev = np.abs(p.sum(axis=1) - 1)
    print(f"{n} predictions; max |sum - 1| = {dev.max():.4f}, {(dev > 0.005).sum()} jets above 0.005")

    rows = slice(args.jet_start, args.jet_start + n)
    with h5py.File(args.original, "r") as f:
        data = {name: f[name][rows] for name in DATASETS}
    jets = data["jets"]
    if len(jets) != n:
        sys.exit(f"original has only {len(jets)} jets from row {args.jet_start}")
    if not (jets["eventNumber"] == pred["eventnumber"].to_numpy()).all():
        sys.exit("eventNumber mismatch: wrong --jet-start or reordered predictions")

    # Same layout as the h5 written during the run: float32 appended to jets.
    merged = np.empty(n, dtype=jets.dtype.descr + [(c, "<f4") for c in PROBS])
    for name in jets.dtype.names:
        merged[name] = jets[name]
    for c in PROBS:
        merged[c] = pred[c].to_numpy(np.float32)
    data["jets"] = merged

    with h5py.File(args.output, "w") as fout:
        for name in DATASETS:
            fout.create_dataset(name, data=data[name])
    print(f"written {args.output}: jets {merged.shape}, {len(merged.dtype.names)} fields")


if __name__ == "__main__":
    main()
