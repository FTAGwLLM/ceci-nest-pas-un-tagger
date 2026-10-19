"""Tagging performance of Opus 5.5 versus GN2 and DL1 (figures 1-3 of the paper).

Input
    ../../data/mc-flavtag-ttbar-medium_w_Opus.h5   jets with truth labels, GN2, DL1 and Claude scores

Output
    fig_01a.png / fig_01b.png   ROC, b vs light / b vs c, AUC in the legend
    fig_02a.png / fig_02b.png   confusion matrices, GN2 / Opus 5.5
    fig_03a.png / fig_03b.png / fig_03c.png
                                D_b scatter, DL1 vs Opus / GN2 vs Opus / DL1 vs GN2

Also prints the AUCs and the Pearson correlations quoted in the text.

Run with:
    python make_performance_plots.py [output_dir]    # default: figures/
"""
import sys
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
JETS_PATH = HERE.parent.parent / "data" / "mc-flavtag-ttbar-medium_w_Opus.h5"
SAVE_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "figures"

TAGGERS = ["Claude", "GN2", "DL1"]
PREFIX = {"Claude": "Claude", "GN2": "GN2v01", "DL1": "DL1dv01"}
PROBS = {"Claude": ["pb", "pc", "pu", "ptau"], "GN2": ["pb", "pc", "pu", "ptau"],
         "DL1": ["pb", "pc", "pu"]}  # DL1 has no tau output

# D_b = ln[ p_b / (fc*p_c + ftau*p_tau + (1 - fc - ftau)*p_u) ]
# These values produce the published figures. The paper text quotes fc = 0.018
# for DL1; with it, DL1 b-vs-c AUC becomes 0.881 instead of 0.897.
FRACTIONS = {
    "Claude": {"fc": 0.2, "ftau": 0.01},
    "GN2":    {"fc": 0.2, "ftau": 0.01},
    "DL1":    {"fc": 0.2, "ftau": 0.0},
}
EPSILON = 1e-6  # guards against log(0) and division by zero

TRUTH_VAR = "HadronGhostTruthLabelID"
TRUTH = {0: "ujets", 4: "cjets", 5: "bjets", 15: "taujets"}
CLASS_ORDER = ["bjets", "cjets", "taujets", "ujets"]
SCATTER_ORDER = ["ujets", "cjets", "bjets", "taujets"]  # b and tau drawn on top
PROB_CLASS = {"pb": "bjets", "pc": "cjets", "pu": "ujets", "ptau": "taujets"}

FLAV_COLOUR = {"ujets": "#029E73", "cjets": "#DE8F05", "bjets": "#0173B2", "taujets": "#CC78BC"}
FLAV_LABEL = {"ujets": "light-jets", "cjets": r"$c$-jets", "bjets": r"$b$-jets",
              "taujets": r"$\tau$-jets"}
TAGGER_COLOUR = {"Claude": "#D55E00", "GN2": "#262626", "DL1": "#949494"}
TAGGER_LS = {"Claude": "-", "GN2": "--", "DL1": ":"}
TAGGER_LABEL = {"Claude": "Opus 5.5", "GN2": "GN2", "DL1": "DL1"}
ROC_ORDER = ["GN2", "DL1", "Claude"]  # Claude drawn last, on top

ROCS = [("fig_01a", r"$b$ vs light", ["ujets"]),
        ("fig_01b", r"$b$ vs $c$", ["cjets"])]
CONFUSION = [("fig_02a", "GN2"), ("fig_02b", "Claude")]
SCATTERS = [("fig_03a", "Claude", "DL1"),  # (name, x tagger, y tagger)
            ("fig_03b", "Claude", "GN2"),
            ("fig_03c", "GN2", "DL1")]


def setup_style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Nimbus Sans", "Liberation Sans", "DejaVu Sans"],
        "mathtext.fontset": "stixsans",
        "font.size": 10, "axes.labelsize": 11, "xtick.labelsize": 10, "ytick.labelsize": 10,
        "legend.fontsize": 9, "legend.title_fontsize": 9,
        "axes.linewidth": 0.8, "axes.grid": False,
        "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True, "ytick.right": True,
        "xtick.minor.visible": True, "ytick.minor.visible": True,
        "xtick.major.size": 4, "ytick.major.size": 4, "xtick.minor.size": 2, "ytick.minor.size": 2,
        "lines.linewidth": 1.5, "legend.frameon": False, "legend.handlelength": 2.2,
        "figure.figsize": (4.2, 3.8), "savefig.dpi": 300,
        "figure.constrained_layout.use": True,
    })


def prob(jets, tagger, name):
    return jets[f"{PREFIX[tagger]}_{name}"]


def discriminant_b(jets, tagger):
    fc, ftau = FRACTIONS[tagger]["fc"], FRACTIONS[tagger]["ftau"]
    p = lambda name: prob(jets, tagger, name).astype(np.float64)
    den = fc * p("pc") + (1 - fc - ftau) * p("pu") + EPSILON
    if "ptau" in PROBS[tagger]:
        den = den + ftau * p("ptau")
    return np.log((p("pb") + EPSILON) / den)


def roc_auc(sig, bkg):
    """(fpr, tpr, auc) scanning the score from the top; tied scores give one point."""
    scores = np.concatenate([sig, bkg])
    is_sig = np.r_[np.ones(len(sig)), np.zeros(len(bkg))]
    order = np.argsort(-scores, kind="stable")
    scores, is_sig = scores[order], is_sig[order]
    last_of_tie = np.r_[np.diff(scores) != 0, True]
    tpr = np.r_[0.0, np.cumsum(is_sig)[last_of_tie] / len(sig)]
    fpr = np.r_[0.0, np.cumsum(1 - is_sig)[last_of_tie] / len(bkg)]
    return fpr, tpr, np.trapezoid(tpr, fpr)


def save(fig, name):
    fig.savefig(SAVE_DIR / f"{name}.png")
    plt.close(fig)
    print(f"written {SAVE_DIR / name}.png")


def plot_roc(truth, d_b, name, title, bkg_flavours):
    is_bkg = np.isin(truth, bkg_flavours)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], ls=":", color="gray", lw=0.8)
    for t in ROC_ORDER:
        fpr, tpr, auc = roc_auc(d_b[t][truth == "bjets"], d_b[t][is_bkg])
        print(f"AUC {title:14s} {TAGGER_LABEL[t]:9s} {auc:.3f}")
        ax.plot(fpr, tpr, color=TAGGER_COLOUR[t], ls=TAGGER_LS[t],
                label=f"{TAGGER_LABEL[t]} (AUC = {auc:.3f})")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_aspect(1 / 1.02, adjustable="box")
    ax.set_xlabel("Background efficiency (FPR)")
    ax.set_ylabel(r"$b$-jet efficiency (TPR)")
    ax.legend(loc="lower right", title=title, alignment="left")
    save(fig, name)


def plot_confusion(jets, truth, name, tagger):
    """Row-normalised; predicted class = argmax (ties go to the first of b, c, light, tau)."""
    cols = [PROB_CLASS[n] for n in PROBS[tagger]]
    p = np.stack([prob(jets, tagger, n) for n in PROBS[tagger]], axis=1)
    predicted = np.array(cols)[np.argmax(p, axis=1)]
    rows = [c for c in CLASS_ORDER if (truth == c).any()]
    cols = [c for c in CLASS_ORDER if c in cols]
    counts = np.array([[np.sum((truth == r) & (predicted == c)) for c in cols] for r in rows])
    fraction = counts / counts.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots()
    image = ax.imshow(fraction, vmin=0, vmax=1, cmap="Blues")
    for i in range(len(rows)):
        for j in range(len(cols)):
            ax.text(j, i, f"{fraction[i, j]:.2f}\n({counts[i, j]})", ha="center", va="center",
                    fontsize=0.8 * plt.rcParams["font.size"],
                    color="white" if fraction[i, j] > 0.5 else "black")
    ax.set_xticks(range(len(cols)), [FLAV_LABEL[c] for c in cols])
    ax.set_yticks(range(len(rows)), [FLAV_LABEL[r] for r in rows])
    ax.minorticks_off()
    ax.tick_params(top=False, right=False, direction="out")
    ax.set_xlabel("Predicted class (highest probability)")
    ax.set_ylabel("Truth class")
    ax.set_title(tagger, fontsize=plt.rcParams["axes.labelsize"])
    fig.colorbar(image, ax=ax, label="Fraction of the truth class", shrink=0.85)
    save(fig, name)


def plot_scatter(truth, d_b, name, x_tagger, y_tagger):
    x, y = d_b[x_tagger], d_b[y_tagger]
    fig, ax = plt.subplots()
    for flav in SCATTER_ORDER:
        sel = truth == flav
        ax.scatter(x[sel], y[sel], s=4, alpha=0.5, linewidths=0, rasterized=True,
                   color=FLAV_COLOUR[flav], label=FLAV_LABEL[flav])
    lo, hi = min(x.min(), y.min()), max(x.max(), y.max())
    pad = 0.03 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    ax.plot([lo, hi], [lo, hi], ls="--", color="gray", lw=0.8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    r = np.corrcoef(x, y)[0, 1]
    print(f"Pearson r D_b {y_tagger} vs {x_tagger}: {r:.3f}")
    ax.text(0.96, 0.04, rf"$r = {r:.3f}$", transform=ax.transAxes, ha="right", va="bottom")
    ax.set_xlabel(rf"$D_b$ ({x_tagger})")
    ax.set_ylabel(rf"$D_b$ ({y_tagger})")
    ax.legend(loc="upper left", markerscale=3, handletextpad=0.2, labelspacing=0.3)
    save(fig, name)


if __name__ == "__main__":
    with h5py.File(JETS_PATH, "r") as f:
        jets = f["jets"][:]
    unknown = ~np.isin(jets[TRUTH_VAR], list(TRUTH))
    if unknown.any():
        sys.exit(f"{unknown.sum()} jets with an unexpected truth label")
    truth = np.array([TRUTH[i] for i in jets[TRUTH_VAR]])
    d_b = {t: discriminant_b(jets, t) for t in TAGGERS}
    if not all(np.isfinite(d).all() for d in d_b.values()):
        sys.exit("non-finite D_b")
    print(f"{len(jets)} jets: " + ", ".join(f"{c} {(truth == c).sum()}" for c in CLASS_ORDER))

    setup_style()
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for name, title, bkg in ROCS:
        plot_roc(truth, d_b, name, title, bkg)
    for name, tagger in CONFUSION:
        plot_confusion(jets, truth, name, tagger)
    for name, x_tagger, y_tagger in SCATTERS:
        plot_scatter(truth, d_b, name, x_tagger, y_tagger)
