# Preprocessing

These scripts rebuild the two h5 files in [`../data`](../data) from the public JetSet file. They are not needed to reproduce the figures, which start from `../data`.

Download `mc-flavtag-ttbar-medium.h5` (~14 GB) from the CERN Open Data record of the ATLAS JetSet sample ([doi:10.7483/OPENDATA.ATLAS.QG8W.TO8P](https://doi.org/10.7483/OPENDATA.ATLAS.QG8W.TO8P)). The commands below assume it is in this folder, and write their outputs to `regenerated/` so that the files shipped in `../data` are left untouched.

**1. Remove the labels**, before inference:

```bash
mkdir -p regenerated
python strip_labels.py --input mc-flavtag-ttbar-medium.h5 \
    --output regenerated/mc-flavtag-ttbar-medium_reco_100k_110k.h5 \
    --jet-start 100000 --jet-stop 110000
```

This step keeps the 7 jet fields and 31 track fields listed in `KEEP`. Truth information, flavour labels and the GN2/DL1 outputs are removed. A safety check refuses any field with "truth" in its name or with a tagger prefix.

**2. Put the labels back**, after inference:

```bash
python attach_labels.py --predictions ../data/predictions.csv \
    --original mc-flavtag-ttbar-medium.h5 \
    --output regenerated/mc-flavtag-ttbar-medium_w_Opus.h5 --jet-start 100000
```

This step checks that the predictions are in input order (`jet_index` and `eventnumber`). It then copies every original field of those jets and appends the four probabilities as float32.

**3. Compare** with the shipped files. Both are byte-identical, so `cmp` prints nothing:

```bash
cmp regenerated/mc-flavtag-ttbar-medium_reco_100k_110k.h5 ../data/mc-flavtag-ttbar-medium_reco_100k_110k.h5
cmp regenerated/mc-flavtag-ttbar-medium_w_Opus.h5 ../data/mc-flavtag-ttbar-medium_w_Opus.h5
```

Both scripts refuse to overwrite an existing output unless `--overwrite` is given.
