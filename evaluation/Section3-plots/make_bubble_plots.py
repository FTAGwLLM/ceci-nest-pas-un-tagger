"""Expression bubble charts for the JetSet run-2 notes.

Reproduces figure 4 of the paper, from the run-2 notes.

Self-contained on purpose: this is the reference for a published figure, so it
carries its own copy of the text pipeline rather than importing it from
`note_word_bubbles_JetSet.ipynb`. Editing the notebook will not silently change
what this script draws. The two only need the data files below.

Inputs (in ../../data)
    predictions.csv                      one row per jet: the four probabilities and the note
    mc-flavtag-ttbar-medium_w_Opus.h5    the same jets with truth labels, row-aligned

Output
    figures/fig_04a.png   expressions, grouped by Claude's own call
    figures/fig_04b.png   the same notes, grouped by truth label

Run with:
    python make_bubble_plots.py [output_dir]    # default: figures/
"""
from __future__ import annotations

import csv
import logging
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

# Fonts without a semibold face fall back to bold, once per label: don't warn each time.
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

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

TOP_N = 36                      # expressions shown per flavour panel
MIN_LABEL_SHARE = 0.03          # a wording must cover this much of a group to name it
FIGURE = "fig_04"               # paper figure number; "a" is by prediction, "b" by truth

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


def make_labels(forms, vocabulary):
    """key -> the wording to print on the bubble."""
    def frequency(word):
        return vocabulary[word] + vocabulary[word + "s"]

    def from_key(key):
        """Build a label for a group Claude never wrote without a quantity in it:
        negation, then qualifiers, then nouns, each ordered commonest-last so the
        head noun ends the phrase -- {high, sd0, trk} -> "high Sd0 trks"."""
        def ordered(words):
            return sorted(words, key=frequency)
        negation = [w for w in key if w in NEGATIONS]
        qualifier = ordered(w for w in key if w in QUALIFIERS and w not in NEGATIONS)
        noun = ordered(w for w in key if w not in NEGATIONS and w not in QUALIFIERS)
        words = negation + qualifier + noun
        surface = forms[key]
        head, total = words[-1], sum(surface.values())
        plural = bool(noun) and re.search(rf"\b{re.escape(head)}s\b", " ".join(surface)) is not None
        counted = sum(n for f, n in surface.items() if VALUE.search(f)) > total / 2
        text = " ".join(DISPLAY_AS.get(w, w) for w in words[:-1] + [head + "s" if plural else head])
        return f"N {text}" if plural and counted else text

    labels = {}
    for key, surface in forms.items():
        total = sum(surface.values())
        plain = {f: n for f, n in surface.items() if not QUANTITY.search(f)}
        # the wording Claude used most often, preferring the shorter one on a tie
        best = min(plain.items(), key=lambda kv: (-kv[1], len(kv[0]))) if plain else None
        # ...but only if it is representative: a phrasing used twice cannot name a group
        # of 900 clauses. "mm trks" occurred 2 times in the 907 clauses that merely count
        # tracks ("4 trks", "3 trks", ...), and `mm` is a stop word, so it named the group
        # after a unit none of the rest mention. Below the threshold, build from the key.
        labels[key] = (best[0] if best and best[1] >= MIN_LABEL_SHARE * total
                       else from_key(key))
    return labels


# ---------------------------------------------------------------------------
# Circle packing and bubble drawing (frozen copies of the notebook's)
# ---------------------------------------------------------------------------
def pack_circles(radii, pad=0.0):
    """Return (x, y) centres for circles with the given radii, packed around the origin."""
    radii = np.asarray(radii, float)
    order = np.argsort(-radii)
    xs, ys, rs = [], [], []
    for k in order:
        r = radii[k]
        if not rs:
            x, y = 0.0, 0.0
        elif len(rs) == 1:
            x, y = rs[0] + r + pad, 0.0
        else:
            X, Y, R = np.array(xs), np.array(ys), np.array(rs)
            cand = []
            n = len(rs)
            for i in range(n):
                for j in range(i + 1, n):
                    di, dj = R[i] + r + pad, R[j] + r + pad
                    dx, dy = X[j] - X[i], Y[j] - Y[i]
                    d = np.hypot(dx, dy)
                    if d == 0 or d > di + dj or d < abs(di - dj):
                        continue
                    a = (di**2 - dj**2 + d**2) / (2 * d)
                    h = np.sqrt(max(di**2 - a**2, 0.0))
                    mx, my = X[i] + a * dx / d, Y[i] + a * dy / d
                    cand.append((mx - h * dy / d, my + h * dx / d))
                    cand.append((mx + h * dy / d, my - h * dx / d))
            cand = np.array(cand)
            # keep candidates that overlap nothing, take the one closest to the centre of mass
            dist = np.hypot(cand[:, None, 0] - X[None], cand[:, None, 1] - Y[None])
            ok = (dist >= R[None] + r + pad - 1e-9).all(1)
            cx, cy = np.average(X, weights=R**2), np.average(Y, weights=R**2)
            cand = cand[ok]
            x, y = cand[np.argmin(np.hypot(cand[:, 0] - cx, cand[:, 1] - cy))]
        xs.append(x); ys.append(y); rs.append(r)
    out = np.zeros((len(radii), 2))
    out[order] = np.column_stack([xs, ys])
    return out

CHAR_W, LINE_H = 0.545, 1.12   # width of a character and height of a line, in units of the font size
MAX_LINES, MAX_FONTSIZE = 4, 24

# a star of the same area as a circle needs this much more outer radius, so that
# "area ∝ occurrences" keeps holding when some bubbles are drawn as stars
STAR_ARMS, STAR_WAIST = 5, 0.42
STAR_SCALE = np.sqrt(np.pi / (STAR_ARMS * STAR_WAIST * np.sin(np.pi / STAR_ARMS)))

def star(centre, radius, arms=STAR_ARMS, waist=STAR_WAIST):
    angles = np.linspace(np.pi / 2, np.pi / 2 + 2 * np.pi, 2 * arms, endpoint=False)
    reach = np.where(np.arange(2 * arms) % 2 == 0, radius, radius * waist)
    return np.column_stack([centre[0] + reach * np.cos(angles), centre[1] + reach * np.sin(angles)])

def wrap(words, n_lines):
    """Break `words` over exactly `n_lines` lines, keeping the longest line as short as possible."""
    if n_lines >= len(words):
        return [[w] for w in words]
    best, best_width = None, None
    for cuts in combinations(range(1, len(words)), n_lines - 1):
        bounds = (0, *cuts, len(words))
        lines = [words[a:b] for a, b in zip(bounds, bounds[1:])]
        width = max(len(' '.join(line)) for line in lines)
        if best_width is None or width < best_width:
            best, best_width = lines, width
    return best

def layout(label, value, radius_pt):
    """Line breaks and font size for a label inside a circle, and whether the count fits too."""
    words = label.split()
    def best_fit(extra):
        best = (0.0, [label])
        for n in range(1, min(MAX_LINES, len(words)) + 1):
            lines = [' '.join(line) for line in wrap(words, n)]
            block = lines + extra
            half_w = CHAR_W * max(len(line) for line in block) / 2
            half_h = LINE_H * len(block) / 2
            fontsize = min(0.95 * radius_pt / np.hypot(half_w, half_h), MAX_FONTSIZE)
            if fontsize > best[0]:
                best = (fontsize, lines)
        return best
    fontsize, lines = best_fit([str(value)])
    if fontsize >= 7:                      # the count only earns its place in a roomy bubble
        return fontsize, lines, True
    return (*best_fit([]), False)

def tint(hex_colour, amount):
    """Mix a colour with white; amount=1 is the full colour."""
    rgb = np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]) / 255
    return tuple(1 - amount * (1 - rgb))

def draw_bubbles(ax, counter, colour, LABEL, top_n=TOP_N, starred=frozenset()):
    """Draw one packed bubble chart of `counter` on an existing axis."""
    ax.set_facecolor(SURFACE); ax.axis('off')
    items = counter.most_common(top_n)
    if not items:
        ax.text(0.5, 0.5, 'nothing to show', ha='center', va='center',
                fontsize=11, color=TEXT_SECONDARY, transform=ax.transAxes)
        return
    labels = [LABEL[k] for k, _ in items]
    values = np.array([n for _, n in items], float)
    radii = np.sqrt(values)                      # area ∝ count
    points = np.array([k in starred for k, _ in items])
    outer = np.where(points, radii * STAR_SCALE, radii)   # room a star needs
    pad = 0.06 * outer.max()                     # visible gap between bubbles
    centres = pack_circles(outer, pad)

    # square window around the packing
    x0, x1 = (centres[:, 0] - outer).min(), (centres[:, 0] + outer).max()
    y0, y1 = (centres[:, 1] - outer).min(), (centres[:, 1] + outer).max()
    cx, cy, half = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) / 2 * 1.02

    ax.set_xlim(cx - half, cx + half); ax.set_ylim(cy - half, cy + half)
    ax.set_aspect('equal')
    pts_per_unit = ax.get_position().width * ax.figure.get_figwidth() * 72 / (2 * half)

    vmax = values.max()
    for (x, y), r, out, pointy, text, v in zip(centres, radii, outer, points, labels, values):
        # stronger tint for more frequent expressions; dark text stays readable on every step
        face = tint(colour, 0.22 + 0.38 * v / vmax)
        ax.add_patch(plt.Polygon(star((x, y), out), facecolor=face, edgecolor=colour, linewidth=1.0)
                     if pointy else
                     plt.Circle((x, y), r, facecolor=face, edgecolor=colour, linewidth=1.0))
        fontsize, lines, show_count = layout(text, int(v), (0.85 * r if pointy else r) * pts_per_unit)
        if fontsize < 4.2:
            continue                             # too small to label; the tables list every expression
        line_h = LINE_H * fontsize / pts_per_unit
        top = y + (len(lines) + show_count - 1) * line_h / 2
        for i, line in enumerate(lines):
            ax.text(x, top - i * line_h, line, ha='center', va='center',
                    fontsize=fontsize, color=TEXT_PRIMARY, fontweight='semibold')
        if show_count:
            ax.text(x, top - len(lines) * line_h, f'{int(v)}', ha='center', va='center',
                    fontsize=0.8 * fontsize, color=TEXT_SECONDARY)

# ---------------------------------------------------------------------------
# The figure: one square panel per flavour on a 2x2 grid
# ---------------------------------------------------------------------------
PANEL_IN, HEAD_IN = 7.5, 1.3    # one panel, and the heading above it, in inches
TITLE_IN = 1.0                  # strip at the top of the figure for its own title
FIG_TITLE_PT = 32               # the figure title; panel headings are smaller
TITLE_PT, SUB_PT = 24, 16       # per-panel heading and subheading, enlarged for print


def panel_axes(n, ncols=2):
    """A figure of n square panels on a grid, each with room for a heading above it,
    under a strip for the figure's own title."""
    nrows = -(-n // ncols)
    fig_w, fig_h = ncols * PANEL_IN, nrows * (PANEL_IN + HEAD_IN) + TITLE_IN
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=SURFACE)
    axes, corners = [], []
    for i in range(n):
        row, col = divmod(i, ncols)
        left = col * PANEL_IN
        top = fig_h - TITLE_IN - row * (PANEL_IN + HEAD_IN)
        axes.append(fig.add_axes([(left + 0.02 * PANEL_IN) / fig_w,
                                  (top - PANEL_IN - HEAD_IN + 0.02 * PANEL_IN) / fig_h,
                                  0.96 * PANEL_IN / fig_w, 0.96 * PANEL_IN / fig_h]))
        corners.append((left, top))
    return fig, axes, corners


def heading(fig, corner, title, subtitle):
    left, top = corner
    fig_w, fig_h = fig.get_size_inches()
    fig.text((left + 0.03 * PANEL_IN) / fig_w, (top - 0.42) / fig_h, title,
             fontsize=TITLE_PT, fontweight="bold", color=TEXT_PRIMARY, va="center")
    fig.text((left + 0.03 * PANEL_IN) / fig_w, (top - 0.84) / fig_h, subtitle,
             fontsize=SUB_PT, color=TEXT_SECONDARY, va="center")


def bubble_figure(counts, labels, jets, keys, word, title):
    """One title for the figure, then a short heading per panel -- the flavour name
    and its counts -- so the rest of the space goes to the bubbles."""
    fig, axes, corners = panel_axes(len(keys))
    fig_w, fig_h = fig.get_size_inches()
    fig.text((0.03 * PANEL_IN) / fig_w, (fig_h - 0.58) / fig_h, title,
             fontsize=FIG_TITLE_PT, fontweight="bold", color=TEXT_PRIMARY, va="center")
    for fl, ax, corner in zip(keys, axes, corners):
        name, colour = FLAVOURS[fl][1], FLAVOURS[fl][2]
        draw_bubbles(ax, counts[fl], colour, labels, top_n=TOP_N)
        heading(fig, corner, name,
                f"{jets[fl]:,} jets {word} this flavour \u00b7 "
                f"top {min(TOP_N, len(counts[fl]))} of {len(counts[fl])} expressions")
    return fig


if __name__ == "__main__":
    rows, predicted, truth, notes = load()
    keys = list(FLAVOURS)

    # one text pipeline, two groupings of the very same clauses
    clauses = build_expressions(predicted, notes)
    vocabulary = vocabulary_of(clauses)
    expression = make_expression(vocabulary)
    forms, by_prediction = tally(clauses, expression, keys)
    _, by_truth = tally(build_expressions(truth, notes), expression, keys)
    labels = make_labels(forms, vocabulary)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for panel, counts, groups, word, title in [
        ("a", by_prediction, Counter(predicted), "called",
         f"Expressions in {MODEL}'s notes, by predicted flavour"),
        ("b", by_truth, Counter(truth), "truly",
         f"Expressions in {MODEL}'s notes, by true flavour"),
    ]:
        name = f"{FIGURE}{panel}"
        fig = bubble_figure(counts, labels, groups, keys, word, title)
        fig.savefig(SAVE_DIR / f"{name}.png", dpi=200, facecolor=SURFACE)
        plt.close(fig)
        print(f"written {SAVE_DIR / name}.png")
