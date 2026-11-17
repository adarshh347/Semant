"""Half-cell mask-interface proxy v1. All equal pair distances are 2d-1 (1,7)."""
import numpy as np

CONTRACT = {'version':'mask-half-cell-colour-excess.v1','d':[1,4],
    'pair_distances_native_cells':[1,7],'mean_excess_threshold_deltaE76':1.,
    'low_mean_activity_threshold_deltaE76':1.,
    'pair_positions_relative_to_left_interface_pixel':'x-3d+2, x-d+1, x+d, x+3d-1',
    'aggregation':'all geometry-supported axis-aligned interfaces; no outcome filtering',
    'interpretation':'conditional on declared thick support, not the whole mask contour'}


def read_interfaces(lab, valid, interfaces):
    a=np.asarray(lab);v=np.asarray(valid)
    if a.dtype.kind not in 'fiu' or a.ndim!=3 or a.shape[2]!=3:raise ValueError('real_Lab_field_required')
    a=a.astype(np.float64)
    if v.dtype!=np.bool_ or v.shape!=a.shape[:2]:raise ValueError('valid_mask_shape')
    if not isinstance(interfaces,list) or not interfaces:raise ValueError('nonempty_interfaces_required')
    if len(interfaces)>1048576:raise ValueError('support_limit')
    for edge in interfaces:
        if not isinstance(edge,list) or len(edge)!=3 or any(type(n)!=int for n in edge) or edge[0] not in (0,1):raise ValueError('canonical_integer_interfaces_required')
    if len(set(tuple(e) for e in interfaces))!=len(interfaces):raise ValueError('duplicate_support')
    result=[]
    for d in (1,4):
        samples=[]
        for off in (-3*d+2,-d+1,d,3*d-1):
            ys=np.array([y+off if axis==0 else y for axis,y,x in interfaces])
            xs=np.array([x+off if axis==1 else x for axis,y,x in interfaces])
            if np.any(ys<0) or np.any(xs<0) or np.any(ys>=a.shape[0]) or np.any(xs>=a.shape[1]):raise ValueError('support_outside_field')
            if not v[ys,xs].all() or not np.isfinite(a[ys,xs]).all():raise ValueError('invalid_selected_support')
            samples.append(a[ys,xs])
        outer_l,near_l,near_r,outer_r=samples
        with np.errstate(over='ignore',invalid='ignore'):
            cross=np.linalg.norm(near_r-near_l,axis=1)
            within=(np.linalg.norm(near_l-outer_l,axis=1)+np.linalg.norm(outer_r-near_r,axis=1))/2
            excess=cross-within;activity=np.maximum(cross,within)
        if not all(np.isfinite(x).all() for x in (cross,within,excess,activity)):raise ValueError('nonfinite_derived_measurement')
        mean=float(excess.mean());active=float(activity.mean())
        result.append({'d':d,'pair_distance_native_cells':2*d-1,'support_count':len(interfaces),
            'cross_deltaE76':cross.tolist(),'within_deltaE76':within.tolist(),'excess_deltaE76':excess.tolist(),
            'mean_excess_deltaE76':mean,'max_excess_deltaE76':float(excess.max()),
            'p95_excess_deltaE76':float(np.quantile(excess,.95)),
            'fraction_excess_above_one':float(np.mean(excess>1)),
            'mean_activity_deltaE76':active,'low_activity_fraction':float(np.mean(activity<1)),
            'status':'nondiagnostic_low_activity' if active<1 else ('mean_no_excess' if mean<=1 else 'mean_excess')})
    return result
