import numpy as np
import pytest
from research.rehearsals.mask_investigation.mask_geometry_gate import inspect_mask


def data():
    rgb=np.zeros((64,64,3),np.uint8);rgb[:,32:]=200
    mask=np.zeros((64,64),bool);mask[:,32:]=True
    return rgb,mask


def test_step_geometry_is_only_candidate():
    r=inspect_mask(*data());assert r['status']=='sampling_candidate'
    assert len(r['supported_interfaces_axis_y_x'])==64
    assert not r['boundary_meaning_verified'] and not r['colour_outcome_computed']


def test_flat_geometry_is_nondiagnostic():
    rgb,mask=data();rgb[:]=128;r=inspect_mask(rgb,mask)
    assert r['geometry_pass'] and r['status']=='not_ready'
    assert 'low_global_signal_nondiagnostic' in r['reasons']


@pytest.mark.parametrize('value',[False,True])
def test_empty_full_preserved(value):
    rgb,mask=data();mask[:]=value;r=inspect_mask(rgb,mask)
    assert r['status']=='not_ready' and not r['geometry_pass']


def test_thin_stripe_no_support():
    rgb,mask=data();mask[:]=False;mask[:,30:32]=True
    assert not inspect_mask(rgb,mask)['geometry_pass']


def test_exact_stride_can_lose_mask():
    rgb=np.zeros((600,600,3),np.uint8);mask=np.zeros((600,600),bool);mask[1,1]=True
    r=inspect_mask(rgb,mask);assert r['stride']==2 and r['native_shape']==[300,300]
    assert 'empty_native_mask' in r['reasons']


def test_transpose_and_complement_preserve_support():
    rgb,mask=data();r=inspect_mask(rgb,mask)
    for a,b in [(rgb.transpose(1,0,2),mask.T),(rgb,~mask)]:
        q=inspect_mask(a,b);assert len(q['supported_interfaces_axis_y_x'])==64
        assert q['status']==r['status']


@pytest.mark.parametrize('bad',['mask_dtype','mask_shape','rgb_dtype'])
def test_bad_frames_refused(bad):
    rgb,mask=data()
    if bad=='mask_dtype':mask=mask.astype(np.uint8)
    if bad=='mask_shape':mask=mask[:-1]
    if bad=='rgb_dtype':rgb=rgb.astype(float)
    with pytest.raises(ValueError):inspect_mask(rgb,mask)


def test_axis_zero_coordinates_are_original_y_x():
    rgb,mask=data();r=inspect_mask(rgb.transpose(1,0,2),mask.T)
    assert r['supported_interfaces_axis_y_x']==[[0,31,x] for x in range(64)]


def test_globally_varied_locally_flat_boundary_can_pass():
    rgb,mask=data();rgb[:]=128;rgb[:,:4]=0
    r=inspect_mask(rgb,mask)
    assert r['status']=='sampling_candidate'
    assert not r['boundary_meaning_verified']
