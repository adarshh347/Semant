"""Synthetic parameter, mass and receipt regressions for the live form study."""
import math

import pytest

from backend.tests.test_perception_lab_derivations import derive
from backend.tests.test_perception_lab_extent_composites import piers
from backend.services.perception_lab.extent_composites import density as DN
from backend.services.perception_lab import form_parameters as FP


@pytest.mark.parametrize('parameters', [
    {'field_shape': []}, {'field_shape': [1]}, {'field_shape': [1, 2, 3]},
    {'field_shape': [0, 2]}, {'field_shape': [129, 2]}, {'field_shape': [2.5, 4]},
    {'field_shape': [True, 4]}, {'field_shape': '44'}, {'field_shape': None},
    {'kernel': 'other', 'bandwidth': 2}, {'kernel': 'gaussian'},
    {'kernel': 'gaussian', 'bandwidth': 0}, {'kernel': 'gaussian', 'bandwidth': -1},
    {'kernel': 'gaussian', 'bandwidth': '2'}, {'kernel': 'gaussian', 'bandwidth': True},
    {'kernel': 'gaussian', 'bandwidth': 129},
])
def test_invalid_parameters_return_a_refusal_receipt_without_a_zero_field(parameters):
    record = derive('extent.density_field', parameters=parameters)
    assert record.payload is None
    assert record.refusals[0].code.value == 'invalid_parameters'
    assert record.requested_parameters == parameters
    assert record.duration_ms >= 0


@pytest.mark.parametrize('bandwidth', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_bandwidth_is_rejected_by_the_shared_validator(bandwidth):
    with pytest.raises(ValueError, match='bandwidth'):
        FP.resolve(DN.FORM, {'kernel': 'gaussian', 'bandwidth': bandwidth})


@pytest.mark.parametrize('kernel', [DN.Kernel('invalid', 1), DN.Kernel('gaussian', 0), DN.Kernel('gaussian')])
def test_direct_producer_obeys_the_same_validation(kernel):
    source = piers()
    result = DN.produce_density_field(source.keys(), sources=[source], field_shape=[4, 4], kernel=kernel)
    assert result.payload is None
    assert any(r.code.value == 'invalid_parameters' for r in result.refusals)


@pytest.mark.parametrize('shape', [[1, 1], [1, 128], [128, 1], [17, 31], [128, 128]])
@pytest.mark.parametrize('sigma', [1e-200, 0.25, 2.0, 128.0])
def test_each_sample_conserves_mass_at_edges_and_on_degenerate_grids(shape, sigma):
    for row, col in [(0, 0), (shape[0]-1, shape[1]-1)]:
        values = DN._spread(row, col, tuple(shape), sigma)
        assert all(math.isfinite(v) and v >= 0 for v in values)
        assert sum(values) == pytest.approx(1, abs=1e-10)


def test_calibration_samples_and_requested_vs_applied_receipts():
    raw = derive(DN.FORM, parameters={'field_shape': [7, 13], 'kernel': 'none', 'bandwidth': 2, 'invented': 9})
    smooth = derive(DN.FORM, parameters={'field_shape': [7, 13], 'kernel': 'gaussian', 'bandwidth': 2})
    assert 'bandwidth' not in raw.parameters
    assert {p.name for p in raw.dropped_parameters} == {'bandwidth', 'invented'}
    assert raw.payload['field']['calibration']['state'] == 'calibrated'
    assert smooth.payload['field']['calibration']['state'] == 'nominal'
    assert smooth.payload['field']['calibration']['units'] is None
    for record in [raw, smooth]:
        field = record.payload['field']
        assert sum(field['inline_values']) == pytest.approx(record.payload['samples_taken'], abs=len(field['inline_values'])*5e-10)
        assert len(record.measurements['centroid_samples']) == record.payload['samples_taken']
        assert record.measurements['bandwidth_units'] == 'grid cells'
        assert record.producible is False  # rendering does not make a deferred form ready


def test_fragment_boolean_is_not_truthy_string_coercion():
    record = derive('extent.fragment_set', parameters={'measure_separation': 'false'})
    assert record.payload is None
    assert record.refusals[0].code.value == 'invalid_parameters'
    valid = derive('extent.fragment_set', parameters={'measure_separation': False})
    assert valid.measurements['separations'] is None
    assert valid.payload['unity_asserted'] is False


def test_typed_form_controls_are_declared_runtime_parameters():
    from backend.services.perception_lab.derivations import DECLARED
    for form in ['extent.fragment_set', DN.FORM]:
        assert {p['name'] for p in FP.declarations(form)} <= set(DECLARED[form])


def test_piazza_branches_read_their_actual_inputs():
    from backend.services.perception_lab.recipes import recipe
    steps = {s.id: s for s in recipe('piazza-negative-space').steps}
    assert steps['pieces'].reads == ('find',)
    assert steps['density'].reads == ('find',)

