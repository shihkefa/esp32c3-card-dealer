"""Flat integrated carrier and companion geometry for V1.0.0.

Native geometry and local fastener records are independent of output paths.
"""
import numpy as np
from types import SimpleNamespace
import formal_carrier_stock as stock
import formal_mounts as mounts

def build(c,w):
    PARTS={p.id:p for p in c.parts}
    UPPER_LIFT=float(c.P['lower_stack_assembly_lift_mm'])
    GEAR_RISE=float(c.P.get('P04B_gear_rise_mm',0.0))
    HEAD_EXTRA_LIFT=1.0+GEAR_RISE
    # The user keeps the already-printed P26. Its historical1mm extension
    # must not grow with the new gear thickness and cancel the head rise.
    P26_EXTENSION_LIFT=1.0
    HEAD_LIFT=c.UPPER_LIFT+HEAD_EXTRA_LIFT
    P04B_GEAR_BOTTOM_Z=36.0
    P04B_GEAR_HEIGHT=c.P04_GEAR_HEIGHT+HEAD_EXTRA_LIFT
    P04B_MATE_Z=c.P04_MATE_Z+HEAD_EXTRA_LIFT
    N20_BASE_Y=-17.5
    
    
    def down_records():
        result=[]
        for x in (-45.,31.):
            for y in (-26.,26.):
                result.append(dict(key=f'hopper.{len(result)+1}',screw_kind='hopperM3x25',
                    nut_kind='hopperM3nut',part='P04A',x=x,y=y,head_z=64.,length_mm=25,
                    nut_bottom_z=40.3,pocket_bottom_z=39.9,pocket_top_z=42.7,
                    entry_xy=[x,y],loading='bottom',entry_bottom_z=10.,
                    axis=[0,0,-1],roof_mm=2.7))
        for x in (-33.,-12.):
            result.append(dict(key=f'n20.{len(result)-3}',screw_kind='n20baseM3x8',
                nut_kind='motorbaseM3nut',part='P04A',x=x,y=N20_BASE_Y,head_z=48.4,length_mm=8,
                nut_bottom_z=41.1,pocket_bottom_z=40.7,pocket_top_z=43.5,
                entry_xy=[x,N20_BASE_Y],loading='bottom',entry_bottom_z=10.,
                axis=[0,0,-1],roof_mm=1.9))
        return result
    
    DOWN_RECORDS=down_records()
    FASTENERS=DOWN_RECORDS+mounts.records()
    DOWN_NUTS=[c.hex_nut3(r['x'],r['y'],r['nut_bottom_z']) for r in DOWN_RECORDS]
    DOWN_SCREWS=[c.flat_screw(r['length_mm']).rot(x=180).move(r['x'],r['y'],r['head_z']) for r in DOWN_RECORDS]
    LOCAL_NUTS=DOWN_NUTS+mounts.nuts(c)
    LOCAL_SCREWS=DOWN_SCREWS+mounts.screws(c)
    NUT_ENTRIES=[]
    DECK_WELLS=[]
    
    def make_carrier():
        a=stock.build(c)
        # Full-height closed nut wells need more wall than the old8mm rail.
        # A12mm round boss provides2.65mm minimum radial wall around6.7mm hex.
        # Both ends finish flush with the existing base and inclined top planes.
        bottom_clip=c.box(220,220,100,0,0,42)
        for r in DOWN_RECORDS:
            if r['loading']=='bottom':
                a+=c.incline(c.cyl(12,35.4,r['x'],r['y'],10))&bottom_clip
        for x,y in c.P04_MOUNTS:
            a-=c.hole(x,y,40,6)
            a-=c.cyl(6.4,1.7,d2=3.4).rot(x=180).move(x,y,45.5)
            well=c.cyl(6.8,40,x,y,45.5)
            DECK_WELLS.append(well)
            a-=well
        for x,y in c.HOUSING_MOUNTS:
            a-=c.hole(x,y,40,9)
            a-=c.cyl(6.4,1.5,x,y,41.9,d2=3.4)
        a-=c.hole(-58,10,40,12)
        # Preserve actual drive envelopes, not the old adapter's obsolete holes.
        for cut in [c.cyly(24.8,25,61,-86.3,54.2),
                    c.cyly(21.3,54.6,61,-27.3,54.2),
                    c.cyly(21.3,10.6,-22,2.7,54),
                    c.cyly(19.6,19.5,61,-59.8,54.2)]:
            a-=c.incline(cut)
        # This was a P31-only clearance. Do not cut the original low flag/hood pads.
        a-=c.box(19,17,45,-47,11,45.4)
        for r in DOWN_RECORDS:
            x,y=r['x'],r['y'];ex,ey=r['entry_xy']
            z=r['pocket_bottom_z'];h=r['pocket_top_z']-z
            if r['loading']=='bottom':
                entry=c.cyl(6.7,r['pocket_top_z']-r['entry_bottom_z'],x,y,r['entry_bottom_z'],n=6)
            else:
                seat=c.cyl(6.7,h,x,y,z,n=6)
                end=c.cyl(6.7,h,ex,ey,z,n=6)
                tunnel=c.S((seat+end).m.hull(),'hull(){'+seat.code+end.code+'}')
                feed=c.cyl(7.2,65-z,ex,ey,z)
                entry=tunnel+feed
            NUT_ENTRIES.append(entry)
            a-=c.incline(entry+c.hole(x,y,20,50))
        for r in mounts.records():
            x,y,z=r['x'],r['y'],r['head_z']
            # Head/tool access from below; the conical seat faces the nut above.
            tool=c.cyl(7.2,z-10,x,y,10)
            cone=c.cyl(6.4,1.5,x,y,z-.2,d2=3.4)
            a-=c.incline(tool+cone+c.hole(x,y,z+1.3,40))
        # Original underside hidden identifier remains off all mating surfaces.
        a-=c.LABEL_BASE_SHAPES['P04A']-PARTS['P04A'].shape
        return a
    
    # Rebuild from clean stock: the old two mounting holes must be filled, not
    # left next to the new bottom-nut axes. Motor and upper-clamp datums stay put.
    P18=c.rr(28,34,3,3,-22,-11,45.4)
    P18+=c.box(4.8,30,10.7,-30.4,-11,48.3)+c.box(4.8,30,10.7,-13.6,-11,48.3)
    P18+=c.box(16,30,.7,-22,-11,48.3)
    for x in (-33,-12):
        P18-=c.hole(x,N20_BASE_Y,44,9)
        P18-=c.cyl(6.4,1.6,d2=3.4).rot(x=180).move(x,N20_BASE_Y,48.5)
        P18-=c.cyl(6.8,25,x,N20_BASE_Y,48.4)
    # Open the inner side of each tool window rather than leaving fragile
    # 0.6/1.6mm slivers of the original tall cradle wall.
    for x in (-30.9,-13.1):
        P18-=c.box(6,6.8,25,x,N20_BASE_Y,48.4)
    for x in (-30.4,-13.6):P18-=c.hole(x,-11,47,16,2.7)
    P18-=c.box(50,15,30,-22,10,43)
    P18-=c.LABEL_BASE_SHAPES['P18']-PARTS['P18'].shape
    def build_p04b():
        # Grow upward only. Keep the1mm gap above P03, bearing shoulder, journal
        # and P06 cross hole at their original datums. Do not cut the old key seat.
        a=(c.gear(60,1.2,P04B_GEAR_HEIGHT,P04B_GEAR_BOTTOM_Z)
           +c.cyl(24.8,P04B_MATE_Z-13,z0=13)+c.cyl(31,3,z0=31,d2=24.8))
        a-=c.cyl(22.5,45,z0=10)
        for angle in range(0,360,60):
            a-=c.annular_sector(18,30,angle+10,angle+50,9+HEAD_LIFT,35)
        a-=c.cylx(3.4,5,-14.5,0,15.5)
        # Bottom-open negative-Y relief aligns with the raised P06 bridge.
        # It stays below the bearing journal and away from the negative-X pin.
        a-=c.box(9,12,2.5,0,-8.75,12.9)
        for x,y in c.P04_MOUNTS:
            a+=(c.cyl(12,P04B_GEAR_HEIGHT,x,y,36)&c.cyl(68.8,P04B_GEAR_HEIGHT,z0=36))
            a-=c.hole(x,y,35.8,7+HEAD_LIFT)
            a-=c.cyl(6.7,4.7+HEAD_LIFT,x,y,35.9,n=6)
        a-=c.LABEL_BASE_SHAPES['P04B']-PARTS['P04B'].shape
        return a
    
    P04B_SHAPE=build_p04b()
    P26_OLD_BOTTOM=float(PARTS['P26'].shape.m.bounding_box()[2])
    P26_SHAPE=PARTS['P26'].shape+c.box(1,7,P26_EXTENSION_LIFT+.02,-74.5,10,P26_OLD_BOTTOM-P26_EXTENSION_LIFT)
    SHAPES={'P04A':make_carrier(),**mounts.build(c,PARTS),'P18':P18,'P04B':P04B_SHAPE,'P26':P26_SHAPE}
    PRINT_ROTATIONS={pid:((0,0,0) if pid=='P04A' else PARTS[pid].print_rot) for pid in SHAPES}
    PRINT_SHAPES={pid:s.rot(*PRINT_ROTATIONS[pid]) for pid,s in SHAPES.items()}
    def pose_part(pid,s):
        extra=HEAD_EXTRA_LIFT if pid in c.RAISED_PRINT_PARTS else 0
        return c.assembly_pose(pid,s).move(z=UPPER_LIFT+extra)
    
    ASSEMBLED={pid:pose_part(pid,s) for pid,s in SHAPES.items()}
    
    DECK_SCREWS=[c.flat_screw(8).rot(x=180).move(x,y,45.4+HEAD_LIFT+UPPER_LIFT) for x,y in c.P04_MOUNTS]
    DECK_NUTS=[c.hex_nut3(x,y,38.2+HEAD_LIFT+UPPER_LIFT) for x,y in c.P04_MOUNTS]
    UPPER_POINTS=[w.UPPER_POINTS[0]]+[(x,y,z+HEAD_EXTRA_LIFT) for x,y,z in w.UPPER_POINTS[1:]]
    UPPER_BUNDLE=w.tube_path(UPPER_POINTS,4)-c.cyl(7.8,8.8,z0=10.5+w.UPPER_LIFT)
    
    def pose_local(s):return c.inclined_head_pose(s).move(z=UPPER_LIFT+HEAD_EXTRA_LIFT)
    
    return SimpleNamespace(**locals())
