"""Theme bar charts for the JetSet run-2 notes.

Reproduces figure 5 of the paper, from the run-2 notes.

Self-contained on purpose: this is the reference for a published figure, so it
carries its own copy of the text pipeline rather than importing it from
`note_word_bubbles_JetSet.ipynb`. Editing the notebook will not silently change
what this script draws. The two only need the data files below.

Inputs (in ../../data)
    predictions.csv                      one row per jet: the four probabilities and the note
    mc-flavtag-ttbar-medium_w_Opus.h5    the same jets with truth labels, row-aligned

Output
    figures/fig_05a.png   themes, grouped by Claude's own call
    figures/fig_05b.png   the same clauses, grouped by truth label

Run with:
    python make_theme_plots.py [output_dir]     # default: figures/
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "data"
CSV_PATH = DATA / "predictions.csv"
JETS_PATH = DATA / "mc-flavtag-ttbar-medium_w_Opus.h5"
SAVE_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "figures"

TRUTH_VAR = "HadronGhostTruthLabelID"
TRUTH_VALUES = {"b": 5, "c": 4, "light": 0, "tau": 15}   # standard ATLAS FTAG convention

# flavour key -> (probability column, label, colour); colours follow the usual ftag convention
FLAVOURS = {
    "b":     ("Claude_pb",   "b-jets",     "#2a78d6"),
    "c":     ("Claude_pc",   "c-jets",     "#eb6834"),
    "light": ("Claude_pu",   "light jets", "#008300"),
    "tau":   ("Claude_ptau", "tau jets",   "#4a3aa7"),
}
MODEL = "Opus 5.5"              # as it appears in the figure titles
TEXT_PRIMARY, TEXT_SECONDARY, SURFACE = "#0b0b0b", "#52514e", "#ffffff"

# Text sizes, enlarged for print; the figure's proportions are unchanged
TITLE_PT, LABEL_PT, AXIS_PT, TICK_PT, LEGEND_PT = 19, 14, 14, 12, 13
FIGURE = "fig_05"               # paper figure number; "a" is by prediction, "b" by truth

# ---------------------------------------------------------------------------
# Load the notes, and group the jets both ways
# ---------------------------------------------------------------------------
def load():
    """Returns (rows, predicted flavour, true flavour, notes)."""
    rows = list(csv.DictReader(open(CSV_PATH)))
    keys = list(FLAVOURS)
    probabilities = np.array([[float(r[FLAVOURS[k][0]]) for k in keys] for r in rows])
    predicted = [keys[i] for i in probabilities.argmax(1)]

    with h5py.File(JETS_PATH, "r") as f:
        jets = f["jets"][:]
    # the CSV carries no truth and its `jet_index` is relative to the slice the run
    # was given, so rows are matched positionally -- which the stored scores confirm
    if len(jets) != len(rows):
        raise SystemExit(f"{len(jets)} jets but {len(rows)} notes; the files are out of step")
    stored = np.column_stack([jets[FLAVOURS[k][0]] for k in keys])
    if not np.allclose(probabilities, stored):
        raise SystemExit("predictions.csv and the jets file are not row-aligned")
    label_of = {v: k for k, v in TRUTH_VALUES.items()}
    truth = [label_of.get(int(t), "other") for t in jets[TRUTH_VAR]]

    return rows, predicted, truth, [r["note"] for r in rows]


# ---------------------------------------------------------------------------
# Text pipeline: notes -> clauses -> expressions -> labels
# (a verbatim copy of the notebook's, frozen here)
# ---------------------------------------------------------------------------
# Clause boundaries: punctuation and the connectives that join two separate arguments
CLAUSE_SPLIT = re.compile(r'[;,]|\bbut\b|\bplus\b|\band\b|\bwith\b|\bwhile\b')

# Shorthand expanded before anything else, so it does not tokenise into debris:
# "w/o IBL" would otherwise become the two meaningless words `w` and `o`
ABBREVIATIONS = [(re.compile(r'\bw/o\b', re.I), 'without'),
                 (re.compile(r'\bincl\.?\b', re.I), ' '),
                 # "b-layer" would otherwise tokenise to a bare `b` and be read as
                 # the b-flavour; it is a detector layer, like the IBL
                 (re.compile(r'\bb[- ]layer\b', re.I), 'blayer')]

# Words carrying no argument of their own. Note that `without` is NOT here: this
# run writes "trks without hits", where the absence is the whole point, so it is
# folded into `no` below instead.
STOP = set('''
a an the and or but of to in on at by for from into onto over under than then as is are was were be
been being it its this that these those there their which who whom whose what when where while so very also
just either nor via vs like plus jet jets gev mev mm um sigma
well exactly otherwise remaining entirely largely essentially up out off still yet even much ish
'''.split())

# Dropped so that "four prompt trks", "all trks prompt" and "prompt trks" are one expression
CARDINALS = set('''
one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen
eighteen nineteen twenty
'''.split())
QUANTIFIERS = set('''
all every each both most rest only single lone few several many
'''.split())
COUNT_WORDS = CARDINALS | QUANTIFIERS

# Spellings folded together before the key is built. This run writes `trk`/`trks`
# where the first run wrote `track`, and reaches for "w/o" and "mm-scale" freely.
SYNONYMS = {
    'displacement': 'displaced', 'undisplaced': 'prompt', 'ips': 'ip',
    'parameter': 'ip', 'parameters': 'ip', 'significance': 'significant', 'sig': 'significant',
    'mildly': 'mild', 'moderately': 'moderate', 'positively': 'positive', 'strongly': 'strong',
    'lacks': 'lack', 'lacking': 'lack', 'missing': 'lack', 'without': 'no',
    'below': 'low', 'under': 'low', 'less': 'low', 'above': 'high', 'over': 'high',
    'big': 'large', 'huge': 'large',
    'track': 'trk', 'tracks': 'trk',    # this run's own abbreviation wins
    'pile': 'pileup',                   # "pile-up" splits on the hyphen
    'm': 'mass', 'bl': 'ibl', 'skewed': 'skew',
}

# Word order used when a label has to be built from the key: negation, then qualifiers, then nouns
NEGATIONS = set('no not lack zero'.split())
QUALIFIERS = set('''
high low large negative positive hard soft clean collimated narrow wide broad diffuse symmetric displaced prompt
moderate mild significant strong weak forward central isolated tight good poor fake genuine leading max net
opposite coherent neutral charged dominated dominant rich secondary same
hitless massive boosted junk material mixed busy messy extreme far collinear shared skew leaning
'''.split())

# Spellings restored for display (capitals elsewhere only mean start of sentence)
DISPLAY_AS = {'sd0': 'Sd0', 'z0': 'z0', 'd0': 'd0', 'ibl': 'IBL', 'v0': 'V0', 'ip': 'IP',
              'k0s': 'K0S', 'k3pi': 'K3pi', 'em': 'EM', 'pt': 'pt', 'ptfrac': 'ptfrac',
              'blayer': 'B-layer'}

TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9]*')   # words may contain digits (Sd0, V0, K0S) but must start with a letter
# a label should quote neither a value nor a quantity that is not part of the key itself
QUANTITY = re.compile(r'\d|\b(?:%s)\b' % '|'.join(sorted(COUNT_WORDS)))
VALUE = re.compile(r'\d|\b(?:%s)\b' % '|'.join(sorted(CARDINALS)))
LESS_THAN = re.compile(r'<|\blow\b|\bbelow\b|\bunder\b|\bless\b')
MORE_THAN = re.compile(r'>|\bhigh\b|\babove\b|\bover\b')


def build_expressions(groups, notes):
    """Count expressions per group. `groups` is one flavour key per note."""
    clauses = []
    for group, note in zip(groups, notes):
        for pattern, replacement in ABBREVIATIONS:
            note = pattern.sub(replacement, note)
        for clause in CLAUSE_SPLIT.split(note):
            clause = clause.strip(" .()")
            if clause:
                clauses.append((group, clause))
    return clauses


def vocabulary_of(clauses):
    """plurals are merged into their singular when the singular also occurs (trks -> trk)"""
    return Counter(t.lower() for _, c in clauses for t in TOKEN.findall(c))


def make_expression(vocabulary):
    def singular(w):
        return w[:-1] if w.endswith("s") and len(w) > 3 and w[:-1] in vocabulary else w

    def expression(clause):
        """Canonical key of a clause: the set of its content words, plus the direction
        of any numeric comparison it makes."""
        text = clause.lower()
        words = []
        for token in TOKEN.findall(text):
            w = SYNONYMS.get(token, singular(token))
            w = SYNONYMS.get(w, w)
            if w not in STOP and w not in COUNT_WORDS:
                words.append(w)
        if LESS_THAN.search(text):
            words.append("low")
        if MORE_THAN.search(text):
            words.append("high")
        return tuple(sorted(set(words)))

    return expression


def tally(clauses, expression, keys):
    """key -> surface forms Claude wrote, and the per-group counts."""
    forms = defaultdict(Counter)
    counts = {fl: Counter() for fl in keys}
    for group, clause in clauses:
        if group not in counts:
            continue
        key = expression(clause)
        if key:
            forms[key][clause.lower()] += 1
            counts[group][key] += 1
    return forms, counts


# ---------------------------------------------------------------------------
# Themes: clauses grouped by the observable they argue from
# ---------------------------------------------------------------------------
THEMES = {
    # --- what the impact parameters look like ---
    'quotes an Sd0 or d0 value':   dict(any={'sd0', 'd0', 'ip'}),
    'tracks are displaced':        dict(any={'displaced'}, without={'no', 'prompt'}),
    'tracks are prompt':           dict(any={'prompt'}),
    'displaced to positive side':  dict(any={'positive'}),
    'displaced to negative side':  dict(any={'negative', 'skew', 'leaning', 'symmetric',
                                             'junk', 'tail', 'outlier'}),
    # --- the size word attached to whatever is being measured ---
    'called mild or small':        dict(any={'mild', 'moderate', 'small', 'tiny', 'slight'}),
    'called strong or large':      dict(any={'strong', 'large', 'clear', 'extreme', 'max'}),
    # --- reasons given to distrust a displacement ---
    'tracks missing inner hits':   dict(any={'ibl', 'blayer', 'pixel', 'hit', 'hitless', 'layer',
                                             'material', 'tracker', 'inner', 'dead'}),
    'pile-up / large z0':          dict(any={'pileup', 'z0'}),
    'V0 or photon conversion':     dict(any={'v0', 'k0s', 'conversion', 'pair', 'shared', 'partner'}),
    # --- the jet rather than its individual tracks ---
    'one track carries the jet':   dict(any={'dominant', 'leading', 'carrying', 'carry', 'fraction',
                                             'ptfrac', 'hardest', 'lead'}),
    'jet or track-pair mass':      dict(any={'mass', 'massive', 'scale'}),
    'net or opposite charge':      dict(any={'charge', 'net', 'sign', 'opposite', 'same'}),
    'jet width / prong structure': dict(any={'narrow', 'collimated', 'collinear', 'prong',
                                             'core', 'axis', 'wide'}),
    'track momentum, hard or soft':dict(any={'hard', 'soft'}),
    'jet pt and direction':        dict(any={'forward', 'pt', 'eta', 'central', 'far', 'boosted'}),
    'names a flavour outright':    dict(any={'b', 'c', 'tau', 'light', 'w', 'k3pi', 'heavy',
                                             'muon', 'ptfrac'}),
}

# Themes are drawn in the order written above, so that opposites sit together.
# These four begin a block; the rule above them is drawn heavier.
FAMILY_STARTS = ['quotes an Sd0 or d0 value', 'called mild or small',
                 'tracks missing inner hits', 'one track carries the jet']

def matches(key, any=frozenset(), without=frozenset(), needs=frozenset()):
    words = set(key)
    return bool(words & any) and not (words & without) and needs <= words

def theme_panel(source, jets, keys, order=None,
                title=None):
    """Themes against flavours, as clauses per 100 jets; returns (figure, rates, row order)."""
    totals = {name: {fl: sum(n for key, n in source[fl].items() if matches(key, **rule))
                     for fl in keys}
              for name, rule in THEMES.items()}
    per_100 = {name: {fl: 100 * n / max(jets[fl], 1) for fl, n in row.items()}
               for name, row in totals.items()}
    if order is None:
        order = list(THEMES)      # as written, so that related themes are adjacent

    fig, ax = plt.subplots(figsize=(8.5, 0.62 * len(order) + 1.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    h = 0.76 / len(keys)
    for i, fl in enumerate(keys):
        y = np.arange(len(order)) - 0.38 + h * (i + 0.5)
        ax.barh(y, [per_100[name][fl] for name in order], height=h * 0.92,
                color=FLAVOURS[fl][2], label=FLAVOURS[fl][1], zorder=2)
    # a rule between themes, so the four bars of one theme read as a group;
    # a heavier one where a block of related themes ends
    for i, y in enumerate(np.arange(len(order) - 1) + 0.5, start=1):
        block = order[i] in FAMILY_STARTS
        ax.axhline(y, color=TEXT_SECONDARY, zorder=1,
                   linewidth=1.1 if block else 0.5, alpha=0.6 if block else 0.35)
    ax.set_ylim(len(order) - 0.5, -0.5)
    ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=LABEL_PT)
    ax.tick_params(axis='y', length=0)
    ax.set_xlabel('clauses per 100 jets of that flavour', fontsize=AXIS_PT, color=TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=TICK_PT)
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(TEXT_SECONDARY)
    ax.legend(frameon=False, fontsize=LEGEND_PT, ncol=2, loc='lower right')
    # the y labels push the axes well to the right, so the title is placed against
    # the figure edge instead of the axes, where it would be clipped
    fig.tight_layout(rect=(0, 0, 1, 0.962))
    fig.text(0.012, 0.986, title, fontsize=TITLE_PT, fontweight='bold',
             color=TEXT_PRIMARY, ha='left', va='top')
    return fig, per_100, order

def theme_table(per_100, order, keys):
    width = max(len(name) for name in order)
    print(f'{"":{width}s}  ' + ''.join(f'{FLAVOURS[fl][1]:>12s}' for fl in keys))
    for name in order:
        print(f'{name:{width}s}  ' + ''.join(f'{per_100[name][fl]:12.1f}' for fl in keys))


if __name__ == "__main__":
    rows, predicted, truth, notes = load()
    keys = list(FLAVOURS)

    # one text pipeline, two groupings of the very same clauses
    clauses = build_expressions(predicted, notes)
    vocabulary = vocabulary_of(clauses)
    expression = make_expression(vocabulary)
    _, by_prediction = tally(clauses, expression, keys)
    _, by_truth = tally(build_expressions(truth, notes), expression, keys)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    # the truth chart keeps the row order of its twin, so the two read side by side
    order = None
    for panel, counts, groups, title in [
        ("a", by_prediction, Counter(predicted),
         f"What {MODEL} argued from, by predicted flavour"),
        ("b", by_truth, Counter(truth),
         f"What {MODEL} argued from, by true flavour"),
    ]:
        name = f"{FIGURE}{panel}"
        fig, rates, order = theme_panel(counts, groups, keys, order, title)
        fig.savefig(SAVE_DIR / f"{name}.png", dpi=200, facecolor=SURFACE)
        plt.close(fig)
        print(f"written {SAVE_DIR / name}.png")
        theme_table(rates, order, keys)
        print()
