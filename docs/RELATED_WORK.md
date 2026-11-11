# Scientific context and related work

## Research question

How do annotation eligibility, neuronal-side selection and normalization affect
observed bilateral cell-type connectivity differences in FAFB v783?

This study contributes a pinned, independently checked example of those choices,
including full row/synapse accounting, release-identity checks and explicit
input-budget denominators. It uses established comparison measures and does not
introduce a cell-matching algorithm or biological-asymmetry test.

## Existing capabilities

| Resource | Relevant capabilities | Role in this study |
| --- | --- | --- |
| [cocoa](https://github.com/flyconnectome/cocoa) | Matched edge-weight comparison, retained connection/synapse fractions, cross-dataset clustering, relative side labels and local connectivity inputs | Appropriate for broader comparative analyses and cross-connectome matching |
| [fafbseg-py](https://github.com/navis-org/fafbseg-py) | Materialization-aware connectivity queries, neuropil selection and proofreading filters | Appropriate for interactive CAVE queries and segmentation access |
| [navis](https://github.com/navis-org/navis) | Morphology analysis, connectivity similarity and matrix aggregation | Appropriate for anatomical analysis and subsequent circuit inspection |
| [FlyWire Codex](https://codex.flywire.ai) | Search, partner exploration, connectivity matrices and interactive neuron views | Appropriate for examining individual neurons and candidate circuits |

In particular, [`cocoa.compare.Comparison`](https://github.com/flyconnectome/cocoa/blob/9c00c303ebc8a0b6e0e50e3798f381730c821aa8/cocoa/compare.py)
already intersects available labels before comparing edge weights and reports
retained connection and synapse fractions. Its FlyWire dataset supports the same
type fallback used here. These are existing capabilities, not shortcomings this
repository claims to fix.

The narrower contribution is a credential-free, reproducible validation workflow:
verify the complete reference input identities; expose alternative annotation
policies; retain both mirrored side relations; report four measurements together;
and independently check every output row and selected published examples. The
[findings](FINDINGS.md) quantify why those choices matter in the reference dataset.

## Published basis

[Schlegel et al., Nature (2024)](https://doi.org/10.1038/s41586-024-07686-5)
already investigated bilateral connectivity stereotypy, technical noise and
normalized connection weights. The study's PLP146 → DNp42 and
LHCENT3 → LHAV3g2 examples, together with its Kenyon-cell counts, provide numerical
anchors here. This analysis does not reproduce the paper's complete Figure 4
population, hemibrain cropping or technical-noise model.

The authors' [v2.1.0 annotation notebook](https://github.com/flyconnectome/flywire_annotations/blob/ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0/code/annotation_counts.ipynb)
explicitly fills missing `cell_type` with `hemibrain_type`. This precedence is
preserved; merged labels remain whole labels rather than duplicated neurons.

[Dorkenwald et al., Nature (2024)](https://doi.org/10.1038/s41586-024-07558-y)
describe the reconstruction and synaptic connectivity. The official
[Zenodo export, version 783.0](https://zenodo.org/records/10676866), supplies
positive pre/post/neuropil counts between proofread neurons. Its input budgets
exclude unproofread partners and therefore do not measure complete anatomical
input. The [methods](METHODOLOGY.md) distinguish this denominator from annotation
coverage and synaptic completion.

## Annotation versions and interpretation

Annotation release v2.1.0 is pinned for publication-era numerical checks. It is
not the newest atlas. The [annotation changelog](https://github.com/flyconnectome/flywire_annotations)
records subsequent revisions, including cross-validation against MaleCNS in
[Berg et al. (2026)](https://doi.org/10.1016/j.cell.2026.08.015) and gustatory
retyping following [Tastekin et al. (2026)](https://doi.org/10.1016/j.cell.2026.08.016).
Historical examples should be checked against current annotations before being
used to motivate anatomical or experimental work.

Source normalization measures output per source neuron; target normalization
measures input per target; pooled input fraction measures a connection's share
of observed target input. These are different questions. Agreement between two
implementations verifies arithmetic under a chosen definition, not biological
validity. Results from one brain cannot establish population-level asymmetry.
