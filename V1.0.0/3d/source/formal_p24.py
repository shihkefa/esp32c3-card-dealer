"""Open P24 seat for the user's measured13x6x10mm exit optointerrupter.

Only the circled redundant pad and front bar are removed. The original backplate,
four1.2mm pin holes, strap slots and hidden ID retain their exact native geometry.
Internal slot/beam/pin geometry remains conditional on the ITR9608-F reference
until physically measured and trial fitted.
"""
from types import SimpleNamespace

def build(c,parts):
    cfg=c.P.get('exit_opto_reference_revision',{})
    shift=float(cfg.get('standard_60mm_seat_Y_shift_mm',1.5))
    body_dims=cfg.get('body_dimensions_XYZ_mm',[13,6,10])
    slot_width=float(cfg.get('conditional_slot_width_mm',5))
    slot_floor=float(cfg.get('conditional_slot_floor_height_mm',4.1))
    old=parts['P24'].shape
    # Keep the main(81,27) pad and its complete original bearing rim. The
    # removed right side starts beyond its X85.5 edge and above the low flange.
    def trim(shape):
        shape-=c.box(30,40,6.35,100.5,13,57.45)
    # Remove the complete protruding front bar without lowering the pad top.
        return shape-c.box(20,3,4,88,21,60.5)-c.box(20,2.1,4,88,20.45,60)
    shape=trim(old)
    unlabelled=trim(c.LABEL_BASE_SHAPES['P24'])
    glyph=c.U(c.box(cell+.03,cell+.03,.37,s,t,-.25)
              for s,t,cell in c.letter_pixels('P24',2.2))
    glyph=glyph.basis((-1,0,0),(0,0,1),(0,1,0),(91,36,64.3))
    engraving=dict(parts['P24'].engraving)
    body=c.box(*body_dims)-c.box(slot_width,body_dims[1]+2,body_dims[2],0,0,slot_floor)
    pins=c.U(c.cyl(.4,6,x,y,-6) for x in (-5,5) for y in (-1.27,1.27))
    pose=lambda s:s.basis((0,0,1),(-1,0,0),(0,-1,0),(91,33+shift,64.3))
    return SimpleNamespace(SHAPE=shape,UNLABELLED=unlabelled,GLYPH=glyph,
        ENGRAVING=engraving,SENSOR_BODY_NATIVE=pose(body),
        SENSOR_PINS_NATIVE=pose(pins),SENSOR_NATIVE=pose(body+pins),
        STANDARD_Y_SHIFT_MM=shift,metadata=dict(
            body_dimensions_XYZ_mm=list(body_dims),body_dimensions_user_confirmed=True,
            slot_width_mm=slot_width,slot_floor_height_mm=slot_floor,
            optical_axis_height_mm=float(cfg.get('conditional_optical_axis_height_mm',6.8)),
            slot_and_pin_dimensions_measured=False,main_mount_axis_native_XY_mm=[81,27],
            original_backplate_geometry_preserved=True,pin_hole_diameter_mm=1.2,
            pin_hole_centers_native_XZ_mm=[[x,z] for x in (89.73,92.27) for z in (59.3,69.3)],
            original_strap_slots_preserved=True,original_ID_preserved=True,
            standard_60mm_seat_Y_shift_mm=shift,narrow_57mm_seat_Y_shift_mm=0.,
            physical_fit_and_feeding_tested=False))
