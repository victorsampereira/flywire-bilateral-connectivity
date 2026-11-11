"""Protect denominators, mirror symmetry, accounting and annotation selection."""

from dataclasses import replace

import pytest

from flywire_bilateral.analysis import Neuron, SynapticEdge, analyze
from flywire_bilateral.io import read_annotations


def population():
    return {
        1: Neuron(1, "A", "left"),
        2: Neuron(2, "A", "right"),
        3: Neuron(3, "B", "left"),
        4: Neuron(4, "B", "right"),
    }


def test_all_edge_rows_partition_and_untyped_inputs_remain_in_budget():
    edges = [
        SynapticEdge(1, 3, 20),
        SynapticEdge(2, 4, 10),
        SynapticEdge(1, 4, 5),
        SynapticEdge(2, 3, 4),
        SynapticEdge(5, 3, 80),
        SynapticEdge(999, 4, 5),
        SynapticEdge(3, 3, 7),
    ]
    result = analyze(population(), edges, known_root_ids={1, 2, 3, 4, 5}, min_total_synapses=1)
    assert sum(result.audit.rows.values()) == len(edges)
    assert sum(result.audit.synapses.values()) == sum(e.syn_count for e in edges)
    assert result.audit.rows == {
        "same": 2,
        "opposite": 2,
        "excluded_annotation": 1,
        "missing_endpoint": 1,
        "autapse": 1,
    }
    assert result.audit.missing_root_ids == {999}
    same = next(r for r in result.comparisons if r.relation == "same")
    assert (same.left_target_input_budget, same.right_target_input_budget) == (104, 20)
    assert same.left_input_fraction == 20 / 104
    assert same.right_input_fraction == 0.5
    assert same.signed_asymmetry > 0 > same.input_fraction_asymmetry


def test_opposite_comparison_uses_destination_population_and_budget():
    neurons = population() | {5: Neuron(5, "B", "right")}
    result = analyze(
        neurons, [SynapticEdge(1, 4, 20), SynapticEdge(2, 3, 10)], min_total_synapses=1
    )
    [row] = result.comparisons
    assert row.relation == "opposite"
    assert (row.left_target_neurons, row.right_target_neurons) == (2, 1)
    assert row.left_per_target == row.right_per_target == 10
    assert (row.left_input_fraction, row.right_input_fraction) == (1, 1)


def test_mirroring_reverses_all_contrasts_and_preserves_absolute_score():
    neurons = population() | {5: Neuron(5, "A", "left")}
    edges = [
        SynapticEdge(1, 3, 12),
        SynapticEdge(2, 4, 8),
        SynapticEdge(1, 4, 2),
        SynapticEdge(2, 3, 6),
    ]
    mirrored = {
        i: replace(n, side="right" if n.side == "left" else "left") for i, n in neurons.items()
    }
    original = {r.relation: r for r in analyze(neurons, edges, min_total_synapses=1).comparisons}
    flipped = analyze(mirrored, reversed(edges), min_total_synapses=1).comparisons
    for row in flipped:
        other = original[row.relation]
        for field in (
            "signed_asymmetry",
            "raw_asymmetry",
            "target_asymmetry",
            "input_fraction_asymmetry",
        ):
            assert getattr(row, field) == pytest.approx(-getattr(other, field))
        assert row.asymmetry_score == other.asymmetry_score


def test_zero_target_budget_is_missing_not_measured_zero():
    [row] = analyze(population(), [SynapticEdge(1, 3, 10)], min_total_synapses=1).comparisons
    assert row.right_input_fraction is None
    assert row.input_fraction_asymmetry is None
    assert row.right_per_source == 0


def test_budget_unchanged_by_report_threshold_and_annotation_policy():
    neurons = population() | {5: Neuron(5, "C", "left"), 6: Neuron(6, "C", "right")}
    edges = [SynapticEdge(1, 3, 100), SynapticEdge(2, 4, 80), SynapticEdge(5, 3, 7)]
    full = analyze(neurons, edges, min_total_synapses=1)
    selected = analyze(population(), edges, known_root_ids=set(neurons), min_total_synapses=100)
    [row] = selected.comparisons
    other = next(r for r in full.comparisons if r.source_type == "A")
    assert row == other


def test_fallback_precedence_and_whole_type_segmentation_exclusion(tmp_path):
    path = tmp_path / "annotations.tsv"
    path.write_text(
        "root_id\tside\tcell_type\themibrain_type\tstatus\n"
        "1\tleft\tA\told_A\t\n2\tright\t\tA\toutlier_seg\n"
        "3\tleft\tB\told_B\toutlier_bio\n4\tright\tB\t\t\n"
        "5\tcenter\tC\t\t\n6\tleft\t\t\t\n"
    )
    result = read_annotations(path)
    assert set(result.neurons) == {3, 4}
    assert result.excluded_seg_types == ["A"]
    assert result.counts == {
        "total": 6,
        "fallback_typed": 1,
        "nonlateral": 1,
        "untyped": 1,
        "excluded_seg_type": 2,
        "eligible": 2,
    }
    assert (
        sum(result.counts[k] for k in ["nonlateral", "untyped", "excluded_seg_type", "eligible"])
        == 6
    )
    assert read_annotations(path, exclude_seg_types=False).neurons[1].cell_type == "A"
    assert 2 not in read_annotations(path, type_policy="cell_type", exclude_seg_types=False).neurons


def test_duplicate_id_in_excluded_row_still_fails(tmp_path):
    path = tmp_path / "a.tsv"
    path.write_text("root_id\tside\tcell_type\n1\tleft\tA\n1\tcenter\t\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_annotations(path)


def test_summing_split_rows_is_invariant_to_order_and_uniform_scale():
    data = population()
    split = [SynapticEdge(1, 3, 4), SynapticEdge(1, 3, 6), SynapticEdge(2, 4, 5)]
    combined = [SynapticEdge(2, 4, 5), SynapticEdge(1, 3, 10)]
    assert (
        analyze(data, split, min_total_synapses=1).comparisons
        == analyze(data, combined, min_total_synapses=1).comparisons
    )
    [original] = analyze(data, split, min_total_synapses=1).comparisons
    [scaled] = analyze(
        data, [replace(e, syn_count=e.syn_count * 7) for e in split], min_total_synapses=1
    ).comparisons
    assert original.signed_asymmetry == scaled.signed_asymmetry
    assert original.left_input_fraction == scaled.left_input_fraction
