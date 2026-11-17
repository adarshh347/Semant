import numpy as np
import pytest
from research.rehearsals.mask_investigation.mask_interface_measurement import read_interfaces

def fixture():
    a=np.zeros((64,64,3));a[:,:,0]=np.arange(64)[None,:]
    return a,np.ones((64,64),bool),[[1,y,31] for y in range(64)]

def test_linear_lab_ramp_exact_equal_distances():
    r=read_interfaces(*fixture())
    for s,p in zip(r,(1,7)):
        assert s['pair_distance_native_cells']==p
        assert s['cross_deltaE76']==[p]*64 and s['within_deltaE76']==[p]*64
        assert s['mean_excess_deltaE76']==0

def test_decreasing_uint_step_no_wrap():
    a,v,e=fixture();a[:]=0;a[:,:32,0]=100
    for s in read_interfaces(a.astype(np.uint8),v,e):assert s['mean_excess_deltaE76']==100

def test_flat_nondiagnostic():
    a,v,e=fixture();a[:]=0
    assert all(s['status']=='nondiagnostic_low_activity' for s in read_interfaces(a,v,e))

def test_sparse_break_mean_hides_local_break():
    a,v,e=fixture();a[:]=0;a[0,32:,0]=100
    r=read_interfaces(a,v,e)
    assert r[0]['max_excess_deltaE76']==100 and r[0]['fraction_excess_above_one']==1/64

def test_transpose_and_reflect():
    a,v,e=fixture();r=read_interfaces(a,v,e)
    assert read_interfaces(a.transpose(1,0,2),v.T,[[0,x,y] for axis,y,x in e])==r
    assert read_interfaces(a[:,::-1],v,e)==r

@pytest.mark.parametrize('kind',['duplicate','bool','bounds','invalid','nan','complex'])
def test_invalid_refuses(kind):
    a,v,e=fixture()
    if kind=='duplicate':e=e+[e[0]]
    if kind=='bool':e[0][0]=True
    if kind=='bounds':e[0][2]=0
    if kind=='invalid':v[:]=False
    if kind=='nan':a[:]=np.nan
    if kind=='complex':a=a.astype(complex)
    with pytest.raises(ValueError):read_interfaces(a,v,e)


def test_global_variation_does_not_rescue_locally_flat_interface():
    a,v,e=fixture();a[:]=0;a[:,:4,0]=100
    assert all(s['status']=='nondiagnostic_low_activity' for s in read_interfaces(a,v,e))
