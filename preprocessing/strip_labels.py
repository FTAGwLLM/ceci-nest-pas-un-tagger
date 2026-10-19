#!/usr/bin/env python3
"""Build the reco-only input given to the model from the ATLAS JetSet sample.

Keeps a contiguous range of jets and only the reconstructed fields listed in
KEEP; truth information, flavour labels and tagger outputs are dropped. The
`eventwise` and `truth_hadrons` datasets are not copied.

Paper input:
    python strip_labels.py --input mc-flavtag-ttbar-medium.h5 \
        --output ../data/mc-flavtag-ttbar-medium_reco_100k_110k.h5 \
        --jet-start 100000 --jet-stop 110000
"""
import argparse
import os
import sys

import h5py
import numpy as np

KEEP = {
    "jets": [
        "pt_btagJes", "eta_btagJes", "pt", "mass", "eta", "phi",
        "eventNumber",  # bookkeeping only, not an inference input
    ],
    "tracks": [
        "numberOfInnermostPixelLayerHits",
        "numberOfNextToInnermostPixelLayerHits",
        "numberOfInnermostPixelLayerSharedHits",
        "numberOfInnermostPixelLayerSplitHits",
        "numberOfPixelHits",
        "numberOfPixelSharedHits",
        "numberOfPixelSplitHits",
        "numberOfSCTHits",
        "numberOfSCTSharedHits",
        "theta", "qOverP", "pt", "ptfrac", "deta", "qOverPUncertainty",
        "d0", "z0SinTheta", "d0Uncertainty", "z0SinThetaUncertainty",
        "phiUncertainty", "thetaUncertainty", "dphi",
        "z0RelativeToBeamspot", "z0RelativeToBeamspotUncertainty",
        "d0RelativeToBeamspot", "d0RelativeToBeamspotUncertainty",
        "lifetimeSignedD0", "lifetimeSignedZ0SinTheta",
        "lifetimeSignedD0Significance", "lifetimeSignedZ0SinThetaSignificance",
        "valid",
    ],
}

# Safety net: none of these may ever reach the output, even if added to KEEP.
FORBIDDEN_FIELDS = {"flavour_label", "jetFoldHash", "ptFinalCalibFromTauJet",
                    "matchedToTauJet", "isJvtHS", "isJvtPU"}
FORBIDDEN_PREFIXES = ("GN2", "DL1")

BATCH_SIZE = 1000


def is_forbidden(field):
    return (field in FORBIDDEN_FIELDS or field.startswith(FORBIDDEN_PREFIXES)
            or "truth" in field.lower())


def copy_dataset(src, dst_file, name, start, stop):
    missing = [f for f in KEEP[name] if f not in src.dtype.names]
    if missing:
        sys.exit(f"{name}: missing fields {missing}")
    bad = [f for f in KEEP[name] if is_forbidden(f)]
    if bad:
        sys.exit(f"{name}: forbidden fields in KEEP {bad}")

    dtype = np.dtype([(f, src.dtype[f]) for f in KEEP[name]])
    dst = dst_file.create_dataset(name, shape=(stop - start,) + src.shape[1:], dtype=dtype)
    for i in range(0, stop - start, BATCH_SIZE):
        j = min(i + BATCH_SIZE, stop - start)
        batch = src[start + i:start + j]
        out = np.empty(batch.shape, dtype=dtype)
        for f in KEEP[name]:
            out[f] = batch[f]
        dst[i:j] = out
    print(f"{name}: kept {len(KEEP[name])} of {len(src.dtype.names)} fields, shape {dst.shape}")


def validate(path, n_rows):
    with h5py.File(path, "r") as f:
        assert set(f.keys()) == set(KEEP), f"datasets: {list(f.keys())}"
        assert not f.attrs, "root attributes present"
        for name, fields in KEEP.items():
            ds = f[name]
            assert ds.shape[0] == n_rows, f"{name}: {ds.shape[0]} rows"
            assert list(ds.dtype.names) == fields, f"{name}: unexpected fields"
            assert not ds.attrs, f"{name}: attributes present"
    print("validation OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="JetSet file (mc-flavtag-ttbar-medium.h5)")
    ap.add_argument("--output", required=True)
    ap.add_argument("--jet-start", type=int, default=100_000)
    ap.add_argument("--jet-stop", type=int, default=110_000, help="exclusive")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if not 0 <= args.jet_start < args.jet_stop:
        sys.exit("need 0 <= jet-start < jet-stop")
    if os.path.exists(args.output) and not args.overwrite:
        sys.exit(f"{args.output} exists, use --overwrite")

    with h5py.File(args.input, "r") as fin, h5py.File(args.output, "w") as fout:
        for name in KEEP:
            if fin[name].shape[0] < args.jet_stop:
                sys.exit(f"{name}: only {fin[name].shape[0]} rows")
            copy_dataset(fin[name], fout, name, args.jet_start, args.jet_stop)

    validate(args.output, args.jet_stop - args.jet_start)


if __name__ == "__main__":
    main()
