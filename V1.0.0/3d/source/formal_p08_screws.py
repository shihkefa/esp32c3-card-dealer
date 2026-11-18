"""Restore the original P08 screw-head holes without changing its tray.

The native stock already contains the original round head entrances and their
conical transitions. Return it directly so every other surface remains exact.
The former nut-pocket builder is retained solely for historical validation.
"""
from types import SimpleNamespace

def build(c,parts):
    return SimpleNamespace(SHAPE=parts['P08'].shape,metadata={
        'scope':'Only restore the two original P08 screw-head holes; other prints and hardware poses unchanged',
        'axes_Y_mm':[-37.5,37.5],'axis_Z_mm':72,
        'through_bore_diameter_mm':3.4,'through_bore_X_range_mm':[35,53],
        'head_bore_diameter_mm':6.4,'head_bore_X_range_mm':[35,39.6],
        'original_cone_diameters_mm':[6.4,3.4],'original_cone_X_range_mm':[39.4,41.1],
        'original_cone_axial_length_mm':1.7,
        'screw_loading_direction':'From original negative-X opening toward positiveX',
        'P09_nut_pockets_unchanged':True,'all_assembled_hardware_poses_unchanged':True,
        'former_P08_nut_pockets_active':False,'physical_fit_validated':False})
