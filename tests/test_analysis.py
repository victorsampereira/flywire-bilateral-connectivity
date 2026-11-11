"""Scientific and computational invariants for bilateral comparisons."""

import math

import pytest

from flywire_bilateral.analysis import Neuron, SynapticEdge, compare_hemispheres


def neurons():
    return {
        1: Neuron(1, "A", "left"),
        2: Neuron(2, "A", "right"),
        3: Neuron(3, "B", "left"),
        4: Neuron(4, "B", "right"),
    }


def test_symmetric_circuit_has_zero_asymmetry():
    results = compare_hemispheres(
        neurons(), [SynapticEdge(1, 3, 20), SynapticEdge(2, 4, 20)], min_total_synapses=1
    )
    assert len(results) == 1
    assert results[0].signed_asymmetry == 0


def test_missing_side_is_ranked_but_not_called_biological():
    [pair] = compare_hemispheres(neurons(), [SynapticEdge(1, 3, 20)], min_total_synapses=1)
    assert pair.signed_asymmetry == 1
    assert pair.left_synapses == 20 and pair.right_synapses == 0


def test_source_population_size_normalization():
    data = neurons() | {5: Neuron(5, "A", "left")}
    [pair] = compare_hemispheres(
        data,
        [SynapticEdge(1, 3, 10), SynapticEdge(5, 3, 10), SynapticEdge(2, 4, 10)],
        min_total_synapses=1,
    )
    assert pair.left_per_source == pair.right_per_source == 10
    assert pair.signed_asymmetry == 0


def test_cross_hemisphere_and_missing_endpoints_are_not_counted():
    edges = [SynapticEdge(1, 4, 100), SynapticEdge(1, 900, 100), SynapticEdge(1, 3, 2)]
    [pair] = compare_hemispheres(neurons(), edges, min_total_synapses=1)
    assert pair.left_synapses == 2
    assert pair.right_synapses == 0


def test_region_split_rows_are_summed():
    [pair] = compare_hemispheres(
        neurons(),
        [SynapticEdge(1, 3, 6), SynapticEdge(1, 3, 4), SynapticEdge(2, 4, 4)],
        min_total_synapses=1,
    )
    assert pair.left_synapses == 10 and pair.right_synapses == 4
    assert math.isclose(pair.signed_asymmetry, 6 / 14)


def test_thresholds_and_type_population_requirements():
    assert compare_hemispheres(neurons(), [SynapticEdge(1, 3, 5)], min_total_synapses=6) == []
    assert (
        compare_hemispheres(
            neurons(), [SynapticEdge(1, 3, 5)], min_total_synapses=1, min_neurons_per_side=2
        )
        == []
    )


def test_deterministic_ordering_by_score_then_count():
    data = neurons() | {5: Neuron(5, "C", "left"), 6: Neuron(6, "C", "right")}
    edges = [SynapticEdge(1, 3, 50), SynapticEdge(2, 4, 50), SynapticEdge(5, 3, 20)]
    ranked = compare_hemispheres(data, edges, min_total_synapses=1)
    assert [(p.source_type, p.target_type) for p in ranked] == [("C", "B"), ("A", "B")]


def test_nonpositive_weight_and_threshold_fail_fast():
    with pytest.raises(ValueError, match="Synapse counts"):
        compare_hemispheres(neurons(), [SynapticEdge(1, 3, 0)], min_total_synapses=1)
    with pytest.raises(ValueError, match="Thresholds"):
        compare_hemispheres(neurons(), [], min_total_synapses=0)
