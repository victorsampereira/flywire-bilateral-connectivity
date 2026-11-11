"""Descriptive bilateral sensitivity analysis; no inference of biological causes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Literal, Mapping

Side = Literal["left", "right"]
Relation = Literal["same", "opposite"]


@dataclass(frozen=True, slots=True)
class Neuron:
    root_id: int
    cell_type: str
    side: Side


@dataclass(frozen=True, slots=True)
class SynapticEdge:
    pre_root_id: int
    post_root_id: int
    syn_count: int


def contrast(left: float, right: float) -> float | None:
    """Signed proportional difference; undefined if both measurements are zero."""
    return (left - right) / (left + right) if left + right else None


@dataclass(frozen=True, slots=True)
class Comparison:
    source_type: str
    target_type: str
    relation: Relation
    left_synapses: int
    right_synapses: int
    left_source_neurons: int
    right_source_neurons: int
    left_target_neurons: int
    right_target_neurons: int
    left_per_source: float
    right_per_source: float
    signed_asymmetry: float
    raw_asymmetry: float
    left_per_target: float
    right_per_target: float
    target_asymmetry: float
    left_target_input_budget: int
    right_target_input_budget: int
    left_input_fraction: float | None
    right_input_fraction: float | None
    input_fraction_asymmetry: float | None

    @property
    def asymmetry_score(self) -> float:
        """Absolute source-normalized contrast, not a significance score."""
        return abs(self.signed_asymmetry)


@dataclass
class EdgeAudit:
    """Mutually exclusive row/synapse partitions, plus nonexclusive diagnostics."""

    rows: Counter[str] = field(default_factory=Counter)
    synapses: Counter[str] = field(default_factory=Counter)
    missing_root_ids: set[int] = field(default_factory=set)

    def add(self, category: str, count: int) -> None:
        self.rows[category] += 1
        self.synapses[category] += count


@dataclass
class Analysis:
    comparisons: list[Comparison]
    audit: EdgeAudit


def analyze(
    neurons: Mapping[int, Neuron],
    edges: Iterable[SynapticEdge],
    *,
    known_root_ids: set[int] | None = None,
    min_total_synapses: int = 100,
    min_neurons_per_side: int = 1,
) -> Analysis:
    """Compare both side relations, with every input row accounted for.

    For opposite-side comparisons, 'left' denotes the SOURCE side: L→R versus
    R→L. Target populations and input budgets follow the destination side.
    Budgets include every non-autaptic input row onto an eligible target,
    including untyped/nonlateral/segmentation-flagged sources. They are totals
    within the supplied file, not estimates of all anatomical synapses.
    Thresholds are applied after summing all neuropil rows. No matching of
    individual neurons and no imputation of unobserved connections is attempted.
    """
    if min_total_synapses < 1 or min_neurons_per_side < 1:
        raise ValueError("Thresholds must be positive integers")
    known = known_root_ids if known_root_ids is not None else set(neurons)
    if not set(neurons) <= known:
        raise ValueError("Eligible neuron IDs must be a subset of known root IDs")
    for key, neuron in neurons.items():
        if key != neuron.root_id or key <= 0 or neuron.side not in ("left", "right"):
            raise ValueError("Invalid neuron identity or side")
        if not neuron.cell_type:
            raise ValueError("Eligible neurons must have a type")
    populations = Counter((n.cell_type, n.side) for n in neurons.values())
    weights: Counter[tuple[str, str, Relation, Side]] = Counter()
    budgets: Counter[tuple[str, Side]] = Counter()
    audit = EdgeAudit()

    for edge in edges:
        if edge.syn_count <= 0:
            raise ValueError("Synapse counts must be positive")
        if edge.pre_root_id <= 0 or edge.post_root_id <= 0:
            raise ValueError("Root IDs must be positive")
        source = neurons.get(edge.pre_root_id)
        target = neurons.get(edge.post_root_id)
        missing = edge.pre_root_id not in known or edge.post_root_id not in known
        if missing:
            audit.missing_root_ids.update(
                root for root in (edge.pre_root_id, edge.post_root_id) if root not in known
            )
        # Denominator is defined independently of source annotation eligibility.
        if target is not None and edge.pre_root_id != edge.post_root_id:
            budgets[target.cell_type, target.side] += edge.syn_count
        if missing:
            audit.add("missing_endpoint", edge.syn_count)
        elif edge.pre_root_id == edge.post_root_id:
            audit.add("autapse", edge.syn_count)
        elif source is None or target is None:
            audit.add("excluded_annotation", edge.syn_count)
        else:
            relation: Relation = "same" if source.side == target.side else "opposite"
            weights[source.cell_type, target.cell_type, relation, source.side] += edge.syn_count
            audit.add(relation, edge.syn_count)

    pairs = {(src, dst, relation) for src, dst, relation, _ in weights}
    results: list[Comparison] = []
    for src, dst, relation in pairs:
        n_l, n_r = populations[src, "left"], populations[src, "right"]
        target_left: Side = "left" if relation == "same" else "right"
        target_right: Side = "right" if relation == "same" else "left"
        t_l, t_r = populations[dst, target_left], populations[dst, target_right]
        if min(n_l, n_r, t_l, t_r) < min_neurons_per_side:
            continue
        left, right = weights[src, dst, relation, "left"], weights[src, dst, relation, "right"]
        if left + right < min_total_synapses:
            continue
        per_left, per_right = left / n_l, right / n_r
        target_per_left, target_per_right = left / t_l, right / t_r
        b_l, b_r = budgets[dst, target_left], budgets[dst, target_right]
        f_l, f_r = left / b_l if b_l else None, right / b_r if b_r else None
        results.append(
            Comparison(
                source_type=src,
                target_type=dst,
                relation=relation,
                left_synapses=left,
                right_synapses=right,
                left_source_neurons=n_l,
                right_source_neurons=n_r,
                left_target_neurons=t_l,
                right_target_neurons=t_r,
                left_per_source=per_left,
                right_per_source=per_right,
                signed_asymmetry=(per_left - per_right) / (per_left + per_right),
                raw_asymmetry=(left - right) / (left + right),
                left_per_target=target_per_left,
                right_per_target=target_per_right,
                target_asymmetry=(target_per_left - target_per_right)
                / (target_per_left + target_per_right),
                left_target_input_budget=b_l,
                right_target_input_budget=b_r,
                left_input_fraction=f_l,
                right_input_fraction=f_r,
                input_fraction_asymmetry=contrast(f_l, f_r)
                if f_l is not None and f_r is not None
                else None,
            )
        )
    results.sort(
        key=lambda c: (
            -c.asymmetry_score,
            -(c.left_synapses + c.right_synapses),
            c.source_type,
            c.target_type,
            c.relation,
        )
    )
    return Analysis(results, audit)


def compare_hemispheres(
    neurons: Mapping[int, Neuron],
    edges: Iterable[SynapticEdge],
    *,
    min_total_synapses: int = 100,
    min_neurons_per_side: int = 1,
) -> list[Comparison]:
    """Compatibility interface returning same-side comparisons only.

    Use ``analyze`` to obtain exclusion accounting and opposite-side results.
    """
    result = analyze(
        neurons,
        edges,
        min_total_synapses=min_total_synapses,
        min_neurons_per_side=min_neurons_per_side,
    )
    return [row for row in result.comparisons if row.relation == "same"]
