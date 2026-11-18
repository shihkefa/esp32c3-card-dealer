"""P2218mm OD x17mm length, with original coaxial motor/roller interfaces.

Clamp axes move0.5mm toward the shaft. The roller clamp also moves0.5mm
toward the middle; its existing M3x8/nut dimensions are preserved.
"""
from types import SimpleNamespace

AXIS_X=61.
AXIS_Z=54.2
OUTER_DIAMETER=18.
LENGTH=17.
START_Y=-58.8
CLAMP_X=65.5
CLAMP_Y=(-55.3,-45.3)
LABEL_ORIGIN=(61.,-58.8,57.8)

def build(c,parts):
    body=c.cyly(OUTER_DIAMETER,LENGTH,AXIS_X,START_Y,AXIS_Z)
    body-=c.cyly(2.15,9.5,61,-59.8,54.2)
    body-=c.cyly(3.15,10.8,61,-50.5,54.2)
    for y in CLAMP_Y:
        body-=c.box(13,8,.6,68.2,y,53.9)
        body-=c.hole(CLAMP_X,y,44,21)
        body-=c.nut(CLAMP_X,y,44.2,8)
        body-=c.cyl(6.4,1.7,d2=3.4).rot(x=180).move(CLAMP_X,y,57.5)
        body-=c.cyl(6.4,8,CLAMP_X,y,57.4)
    # Retain the actual original hidden glyph and move it to the new end face.
    glyph=(c.LABEL_BASE_SHAPES['P22']-parts['P22'].shape).move(y=.5)
    screws=[c.flat_screw(8).rot(x=180).move(CLAMP_X,y,57.4) for y in CLAMP_Y]
    nuts=[c.hex_nut3(CLAMP_X,y,49.7) for y in CLAMP_Y]
    return SimpleNamespace(SHAPE=body-glyph,UNLABELED=body,GLYPH=glyph,SCREWS=screws,NUTS=nuts,
        metadata={'outer_diameter_mm':18,'axial_length_mm':17,'axial_Y_mm':[-58.8,-41.8],
            'axis_XZ_mm':[61,54.2],'coaxial_bore_diameters_mm':[2.15,3.15],
            'bore_positions_and_depths_unchanged':True,'clamp_axes_XY_mm':[[65.5,y] for y in CLAMP_Y],
            'local_clamp_translations_mm':[[-.5,0,0],[-.5,-.5,0]],
            'screw_and_nut_sizes_unchanged':True,'physical_fit_tested':False})
