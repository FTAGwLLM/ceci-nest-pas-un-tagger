# Data

The 10,000 jets of the paper are rows `[100000, 110000)` of `mc-flavtag-ttbar-medium.h5` from the ATLAS JetSet sample ([doi:10.7483/OPENDATA.ATLAS.QG8W.TO8P](https://doi.org/10.7483/OPENDATA.ATLAS.QG8W.TO8P)). Row `i` of every file below is the same jet.

| File | Content |
|---|---|
| `mc-flavtag-ttbar-medium_reco_100k_110k.h5` | Inference input: reconstructed jet and track fields only, as given to the model. No truth, no tagger outputs. |
| `predictions.csv` | Output of the run: `jet_index`, `eventnumber`, `Claude_pb`, `Claude_pc`, `Claude_pu`, `Claude_ptau`, and the free-text `note`. |
| `mc-flavtag-ttbar-medium_w_Opus.h5` | All original JetSet fields for the same jets (truth labels, GN2, DL1, ...) plus the four `Claude_*` probabilities. Every figure in the paper is made from this file. |

`SHA256SUMS` lists the checksums. Both `.h5` files can be rebuilt from JetSet with the scripts in [`../preprocessing`](../preprocessing).

The h5 files contain two datasets: `jets` (one row per jet) and `tracks` (40 tracks per jet, padded, `valid` marks real tracks).

Truth flavour is `jets/HadronGhostTruthLabelID`: 5 = b, 4 = c, 15 = τ, 0 = light. Reference taggers are `GN2v01_p{b,c,u,tau}` and `DL1dv01_p{b,c,u}`.
