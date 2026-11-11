# Findings from the full v783 run

Executed locally on 10 November 2026 and reproduced, with an identical report
checksum, on a GitHub-hosted runner ([run 42939139229](https://github.com/victorsampereira/flywire-bilateral-connectivity/actions/runs/42939139229)).
These are reproducible observations about
an analysis workflow, **not a discovery of biological asymmetry**. Machine-readable
counts, examples and the report checksum are in [reference_results.json](reference_results.json).
All tables below derive from the official data identified by [the manifest](data_manifest.json).

## 1. Type-field selection changes coverage

The annotation file and the independent proofread-ID array contain exactly the
same **139,255** root IDs. All **16,847,997** pre/post/neuropil rows join to these
IDs. They carry **54,492,922** synapses; no autapse rows were found. Root consistency
is thus established for these specific files, not for arbitrary v783-labelled files.

| Annotation policy | Eligible lateral neurons | Same-side synapses | Opposite-side synapses |
| --- | ---: | ---: | ---: |
| `cell_type` only, retain segmentation types | 110,997 | 24,661,761 | 2,519,986 |
| Combined types, retain segmentation types | 131,681 | 42,008,967 | 7,566,388 |
| Combined types, exclude entire segmentation-flagged types (default) | 129,945 | 40,905,592 | 7,026,166 |

The first two runs isolate the type fallback: it restores **20,684 eligible
lateral neurons**, while **20,721** annotations gain a type before laterality
filtering. Using only `cell_type` retains 24.66M same-side synapses; applying the
published fallback retains 42.01M. The fallback is already implemented upstream;
this controlled comparison quantifies the effect of omitting it.

Default annotation exclusions are 7,444 untyped neurons, 130 typed nonlateral
neurons and 1,736 lateral neurons belonging to 210 types containing segmentation
outliers. These are eligibility exclusions, not proof that those neurons are
unusable. The default edge audit excludes 6,561,164 synapses for annotation
eligibility, retains 40,905,592 same-side and 7,026,166 opposite-side synapses,
and loses zero synapses to missing IDs.

## 2. Independent numerical anchors reproduce exactly

These checks were chosen from [Schlegel et al. (2024)](https://doi.org/10.1038/s41586-024-07686-5)
before reading connectivity results. A separate DuckDB SQL implementation,
which does not import our analysis or annotation reader, computes them directly
from the downloaded files.

| Reference | Published left / right | Observed left / right |
| --- | ---: | ---: |
| PLP146 → DNp42, same-side synapses | 0 / 34 | 0 / 34 |
| LHCENT3 → LHAV3g2, same-side synapses | 30 / 23 | 30 / 23 |
| Kenyon-cell population | 2,580 / 2,597 | 2,580 / 2,597 |

The first source's `hemibrain_type` is PLP146, but its preferred `cell_type` is
**LTe56**. All members of the second circuit use the hemibrain fallback in this
release. Both circuit examples are absent when selecting only nonempty `cell_type`.
Neither passes the default 100 combined-synapse reporting threshold; the
reference checker deliberately tests them directly, independently of that filter.

For inspection, LTe56 has roots `720575940634155731` (left) and
`720575940627849994` (right); DNp42 has `720575940618594022` (left) and
`720575940641148149` (right). Use materialization 783 when viewing these IDs.
The paper treats the 30/23 difference as compatible with technical noise;
reproducing its numbers does not independently reproduce that noise model.

## 3. Excluding opposite-side edges hides large, relatively balanced connections

The default ≥100-synapse report contains **48,986** pair/relation rows:
38,541 same-side and **10,445 opposite-side**. These relation rows are not unique
anatomical circuits: a type pair can appear in both relations.

An illustrative post hoc example is **Tm9 → CT1** in the opposite relation:
24,554 synapses from left-source Tm9 to right-labelled CT1, and 23,466 in the
mirror comparison. With 756/750 source neurons and one target on each side,
source-normalized contrast is only **+0.0187**. A same-side-only selection omits
this substantial connection. This observation concerns annotated neuronal sides,
not a claim that these synapses physically cross the brain midline.

## 4. Normalization can change the apparent direction

For **PS137 → CB2825**, same-side counts are 188/403. There are two source
neurons on each side, but two left and four right targets:

| Measure | Left | Right | Signed contrast |
| --- | ---: | ---: | ---: |
| Synapses per source | 94.0 | 201.5 | −0.3638 |
| Synapses per target | 94.0 | 100.75 | −0.0347 |
| Share of observed target inputs | 22.82% | 14.30% | +0.2294 |

Target input budgets are 824/2,818. Source normalization alone suggests a large
rightward count difference. Per-target normalization is nearly balanced, while
the input share is greater on the left. These quantities answer different
questions; none establishes the biologically correct interpretation.

An even more extreme historical example, CB0980 → JO-E, has 65/1,654 synapses
but **5/189 target neurons**. Source contrast is −0.9099; target contrast is
+0.1953; input-fraction contrast is +0.2689. It is an example to check the
population/ontology before discussing asymmetry. Johnston's Organ annotations
were subsequently revised in v3.1.0; this publication-era result is **not** an
annotation correction proposal for today's atlas.

| Combined-weight threshold | Report rows | Opposite signs: per-source vs input-fraction | Opposite signs with both absolute contrasts ≥0.2 |
| --- | ---: | ---: | ---: |
| 100 | 48,986 | 11,572 | 160 |
| 500 | 7,716 | 2,354 | 9 |
| 1,000 | 4,137 | 1,394 | 2 |

The 0.2 cutoff is an explicitly exploratory magnitude filter, not statistical
significance. Many sign changes are close to zero, and stronger connections can
have small proportional differences. The table is evidence that the measurement
choice matters; it does not quantify a rate of biological asymmetry. The examples
in sections 3–4 were selected after examining results, unlike the published anchors.

## Verification and practical value

Independent SQL agrees with all counts, populations, budgets and numeric measures
in **all 48,986** default rows (floating-point tolerance 1e-12; zero mismatches).
A second full run produces byte-identical CSV. The initial run took **30.58 s**
wall time and reached **1,407,614,976 bytes (~1.31 GiB) maximum resident memory**
on this macOS arm64 machine with Python 3.15.2. Subsequent runs took 43.5–61.3 s
under concurrent work; these are local measurements, not a portable benchmark.

The concrete contribution is a checked example of how a plausible analysis can
lose valid populations and produce denominator-sensitive interpretations. A
researcher can reproduce it without credentials, inspect the exact inclusion
rules, and reuse the audit/denominator checks in their workflow. Existing tools
already implement comparative connectivity. This analysis establishes
computational consistency and measurement sensitivity; biological interpretation
and generalization require further evidence.
