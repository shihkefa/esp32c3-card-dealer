"""Trim only the two P16 axial end faces, keeping all working interfaces.

Both ends lose0.5mm. The two ring grooves move fromY+/-24 to+/-21. The
original hidden glyph moves to the new negative-Y face without an old void.
"""
from types import SimpleNamespace

def build(c,parts):
    original_unlabelled=c.LABEL_BASE_SHAPES['P16']
    clip=c.box(40,53,40,61,0,34.2)
    restored=original_unlabelled
    for center in (-24,24):
        # Overlap already-solid material by0.01mm radially and0.02mm at
        # each axial edge, avoiding numerically separate coplanar rings.
        restored+=c.cyly(18.4,2.34,61,center-1.17,54.2)-c.cyly(16.78,2.6,61,center-1.3,54.2)
    # Filling the old outer grooves must not fill the original axial split.
    restored-=c.box(13,54.2,.6,68.7,0,53.9)
    unlabelled=restored&clip
    for center in (-21,21):
        unlabelled-=c.cyly(22,2.3,61,center-1.15,54.2)-c.cyly(16.8,2.6,61,center-1.3,54.2)
    glyph=(original_unlabelled-parts['P16'].shape).move(y=.5)
    return SimpleNamespace(SHAPE=unlabelled-glyph,UNLABELED=unlabelled,GLYPH=glyph,
        metadata={'old_axial_length_mm':54,'new_axial_length_mm':53,
            'old_native_Y_mm':[-27,27],'new_native_Y_mm':[-26.5,26.5],
            'trim_per_end_mm':.5,'main_axis_native_XZ_mm':[61,54.2],
            'bore_diameter_mm':3.15,'hub_clamp_and_hardware_positions_unchanged':True,
            'old_O_ring_groove_centers_Y_mm':[-24,24],'O_ring_groove_centers_Y_mm':[-21,21],
            'O_ring_shift_toward_center_mm_each':3,'O_ring_groove_width_mm':2.3,
            'O_ring_groove_root_diameter_mm':16.8,'groove_to_end_solid_land_mm':4.35,
            'original_annular_lightening_cavity_retained':True,'nominal_groove_to_cavity_radial_wall_mm':1.9,
            'hidden_label_origin_mm':[61,-26.5,59.7],
            'glyph_translation_native_mm':[0,.5,0],'qty':2,
            'physical_fit_and_feeding_tested':False})
