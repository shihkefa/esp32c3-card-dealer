"""WX22-12PS native print geometry and reference harness, part of V1.0.0.

Geometry preserves the completed design; actual printed clamping and cable
fit remain unverified. All geometry is constructed without file-system input.
"""
import math
import numpy as np
from types import SimpleNamespace
import formal_p06 as p6
from formal_p06 import build as build_p06

def build(c):
    PARTS={p.id:p for p in c.parts}
    BOTTOM=0.0
    FLOOR_TOP=2.2
    SLIP_POST_HEIGHT=23.0
    UPPER_LIFT=22.2
    # P01/slip-ring construction stays fixed; only the seated upper mechanism
    # uses the independently lowered assembly frame.
    ASSEMBLY_LOWER_LIFT=float(c.P['lower_stack_assembly_lift_mm'])
    # Only the outer wall and four cover-column tops are2mm shorter.
    # Purchased parts,23mm slip-ring supports and assembly frames stay put.
    P01_TOP_TRIM=2.0
    SHELL_TOP=29.9+UPPER_LIFT-P01_TOP_TRIM
    COVER_NUT_STOP=10.8+UPPER_LIFT
    FLANGE_BOTTOM=FLOOR_TOP+SLIP_POST_HEIGHT
    FLANGE_TOP=FLANGE_BOTTOM+2.5
    COVER_CENTERS=[(x,y) for x in (-68,68) for y in (-58,58)]
    FLANGE_ANGLES=(30,150,270)
    FLANGE_CENTERS=[(17.5*math.cos(math.radians(a)),17.5*math.sin(math.radians(a))) for a in FLANGE_ANGLES]
    TIE_LOCATIONS=[(x,y+dy) for x,y in [(-58,-2),(-26,-38),(22,-42),(-68,-36),(-20,55),(25,55)]
                   for dy in ((-13.4,13.4) if y==55 else (-7,7))]+[(-30,17),(-30,27)]
    
    
    def tie_anchor(x,y):
        shell=c.rr(10,4,1,3.8,x,y,2.2)
        passage=c.poly([(-3,2.3),(3,2.3),(0,5.3)],6).rot(x=90).move(x,y+3)
        return shell-passage
    
    def tube_path(points,d):
        """Spherical-ended segments conservatively enclose a round flexible cable."""
        points=[np.asarray(p,dtype=float) for p in points]
        pieces=[]
        for p in points:
            pieces.append(c.S(c.mf.Manifold.sphere(d/2,16),'').move(*p))
        for a,b in zip(points,points[1:]):
            axis=b-a;length=float(np.linalg.norm(axis));axis/=length
            seed=np.array([1.,0,0]) if abs(axis[0])<.8 else np.array([0.,1,0])
            u=np.cross(seed,axis);u/=np.linalg.norm(u);v=np.cross(axis,u)
            pieces.append(c.cyl(d,length,n=16).basis(u,v,axis,a))
        return c.U(pieces)
    
    def lower_points(x):
        # Individual0.85mm leads fan into flat rows; this is an unmeasured trial
        # arrangement, not a claim that a3.5mm bundle can make this bend.
        exit_z=FLANGE_BOTTOM-17
        bend_z=exit_z-.5
        points=[(x,0,exit_z),(x,0,bend_z)]
        points += [(x,4-4*math.cos(t),bend_z-4*math.sin(t)) for t in np.linspace(0,math.pi/2,17)[1:]]
        points.append((x,28,bend_z-4))
        return points
    
    LOWER_POINTS=[lower_points(x+offset) for x in (-6,6) for offset in np.linspace(-2.25,2.25,6)]
    UPPER_POINTS=[(0,0,19.3+UPPER_LIFT),(0,0,47+ASSEMBLY_LOWER_LIFT)]
    UPPER_POINTS += [(0,8-8*math.cos(t),47+ASSEMBLY_LOWER_LIFT+8*math.sin(t)) for t in np.linspace(0,math.pi/2,17)[1:]]
    UPPER_POINTS.append((0,18,55+ASSEMBLY_LOWER_LIFT))
    LOWER_WIRES=[tube_path(points,.85)-c.cyl(22,17,z0=FLANGE_BOTTOM-17) for points in LOWER_POINTS]
    LOWER_BUNDLES=[c.U(LOWER_WIRES[:6]),c.U(LOWER_WIRES[6:])]
    LOWER_BUNDLE=c.U(LOWER_BUNDLES)
    UPPER_BUNDLE=tube_path(UPPER_POINTS,4.0)-c.cyl(7.8,8.8,z0=10.5+UPPER_LIFT)
    
    def teardrop_y(x,y0,y1,z,r=3.3):
        profile=[(r*math.cos(a),r*math.sin(a)) for a in np.linspace(math.pi,2*math.pi,25)]
        profile.append((0,r))
        return c.poly(profile,y1-y0).rot(x=90).move(x,y1,z)
    
    WIRE_GUIDES=c.U(c.rr(1,14,.4,1.4,x+dx,21,FLOOR_TOP) for x in (-6,6) for dx in (-3.4,3.4))
    SLIP_STANDOFFS=c.U(c.cyl(10,SLIP_POST_HEIGHT,x,y,FLOOR_TOP)
                       +c.cyl(14,2,x,y,FLOOR_TOP,d2=10) for x,y in FLANGE_CENTERS)
    
    def build_p01():
        # Original thin flat floor and a taller hollow perimeter. No raised slab,
        # false floor, closed wiring duct or full-area pedestal is present.
        base=c.rr(164,148,16,2.2,z0=BOTTOM)
        base=base+(c.rr(164,148,16,27.8+UPPER_LIFT-P01_TOP_TRIM,z0=2.1)
                   -c.rr(159.6,143.6,13.8,29+UPPER_LIFT,z0=2))
        base=base-c.box(26,7,4,0,-74,26.6+UPPER_LIFT)
        for x,y in COVER_CENTERS:
            base=base+c.cyl(14,UPPER_LIFT-1.9,x,y,2)+c.cyl(16,2,x,y,2,d2=14)
            base=base+c.cyl(14,2,x,y,UPPER_LIFT,d2=10)
            base=base+c.cyl(10,SHELL_TOP-(UPPER_LIFT+2),x,y,UPPER_LIFT+2)
            base=base-c.hole(x,y,1,30+UPPER_LIFT)
            # Generous lower tool well, 45deg hex taper, short captive hex seat.
            base=base-c.cyl(10,UPPER_LIFT+.1,x,y,-.1,n=6)
            base=base-c.cyl(10,1.65,x,y,UPPER_LIFT,n=6,d2=6.7)
            base=base-c.cyl(6.7,9.16,x,y,UPPER_LIFT+1.64,n=6)
        base=base+SLIP_STANDOFFS+WIRE_GUIDES
        for x,y in FLANGE_CENTERS:
            # Short hollow locating pegs center the purchased5.5mm flange holes.
            # Their top stays0.3mm below the flange/washer contact face.
            base=base+c.cyl(5.1,2.2,x,y,FLANGE_BOTTOM)
            head_z=FLANGE_BOTTOM-2.5
            base=base-c.hole(x,y,head_z-.1,9.2)
            base=base-c.cyl(6.4,1.7,x,y,head_z,d2=3.4)
            base=base-c.cyl(7.2,head_z+.1,x,y,-.1)
        base=base-c.box(8,11,5,-81,-36.5,6.7)-c.box(8,9,14.8,81,-1,7.35)
        for x,y in TIE_LOCATIONS:base=base+tie_anchor(x,y)
        # Original hidden P01 identifier on the inside floor remains unchanged.
        base=base-(c.LABEL_BASE_SHAPES['P01']-PARTS['P01'].shape)
        return base
    
    P01=build_p01()
    LOCAL_P06=build_p06(c)
    P06=LOCAL_P06.move(z=ASSEMBLY_LOWER_LIFT)
    SHAPES={'P01':P01,'P06':P06}
    PRINT_SHAPES={'P01':P01,'P06':LOCAL_P06}
    STATOR=c.cyl(22,17,z0=FLANGE_BOTTOM-17)+c.cyl(44,2.5,z0=FLANGE_BOTTOM)
    for x,y in FLANGE_CENTERS:STATOR=STATOR-c.hole(x,y,FLANGE_BOTTOM-.1,2.7,5.5)
    ROTOR=c.cyl(22,5,z0=FLANGE_TOP)+c.cyl(7.8,8.8,z0=FLANGE_TOP+5)
    SLIP_SCREWS=[c.flat_screw(8).move(x,y,FLANGE_BOTTOM-2.5) for x,y in FLANGE_CENTERS]
    SLIP_WASHERS=[c.cyl(7,.5,x,y,FLANGE_TOP)-c.cyl(3.2,.7,x,y,FLANGE_TOP-.1) for x,y in FLANGE_CENTERS]
    SLIP_NUTS=[c.hex_nut3(x,y,FLANGE_TOP+.5) for x,y in FLANGE_CENTERS]
    P06_SCREWS=[s.move(z=ASSEMBLY_LOWER_LIFT) for s in p6.screws(c)]
    P06_NUTS=[s.move(z=ASSEMBLY_LOWER_LIFT) for s in p6.nuts(c)]
    COVER_NUTS=[c.hex_nut3(x,y,8.4+UPPER_LIFT) for x,y in COVER_CENTERS]
    
    # Scene placement changes, while the other printed part geometries remain
    # byte-for-byte reusable. Bottom electronics and battery stay on their floor.
    BOTTOM_PRINT_IDS={'P01','P29','P36'}
    BOTTOM_HARDWARE={'batteryholder','18650','ESP32C3','charger','TypeC','booster',
                     'protection1S','ULN2003','powerrocker'}
    def reference_shift(kind,is_print=False):
        return 0 if kind in (BOTTOM_PRINT_IDS if is_print else BOTTOM_HARDWARE) else ASSEMBLY_LOWER_LIFT
    
    return SimpleNamespace(**locals())
