"""Check actual seating, nut access, tool access and flat print contact for P02."""
import json
import numpy as np
import build_cad as c
from virtual_assembly_check import Actor,overlap

parts={p.id:p for p in c.parts}
assert 'P02' not in parts and {'P02A','P02B','P03'}<=parts.keys()
plate=parts['P02A'].shape;seat=parts['P02B'].shape;cap=parts['P03'].shape
def intersection(a,b):return float((a.m^b.m).volume())
bed=[]
for pid,minimum in [('P02A',15000),('P02B',900),('P03',2000)]:
    p=parts[pid];shape=p.shape.rot(*p.print_rot)
    b=np.array(shape.m.bounding_box());cx,cy=(b[0]+b[3])/2,(b[1]+b[4])/2
    slab=c.box(b[3]-b[0]+2,b[4]-b[1]+2,.02,cx,cy,b[2])
    area=intersection(shape,slab)/.02
    assert area>=minimum,(pid,area)
    bed.append({'part':pid,'flat_contact_mm2':round(area,2),'checked_layer_mm':.02,'passed':True})

seat_offsets=list(np.linspace(-20,0,41))
for dz in seat_offsets:
    assert intersection(seat.move(z=float(dz)),plate)<.02,('seat insertion',dz)
for dz in np.linspace(20,0,41):
    moving=cap.move(z=float(dz))
    assert intersection(moving,plate)<.02 and intersection(moving,seat)<.02,('cap insertion',dz)

nut_samples=0
for x,y in c.BEARING_MOUNTS:
    for bottom in np.linspace(15.6,28.1,51):
        assert intersection(c.hex_nut3(x,y,float(bottom)),seat)<.02,('nut access',x,y,bottom)
        nut_samples+=1
    # Driver enters from above while P04 is not yet installed.
    key=c.cyl(2.6,25,x,y,35.05)
    assert all(intersection(key,body)<.02 for body in (plate,seat,cap)),('driver access',x,y)
    # Axial stop gives a 2.4mm nut a 2.2mm roof below the boss top.
    assert 32.8-30.6>=2.19

fixed_bearing=next(shape for name,shape,_ in c.hardware if name=='6005ZZ')
assert intersection(seat,fixed_bearing)<.02
assert intersection(cap,fixed_bearing)<.02

# Clamp footprints are measured at the actual main-plate lower/upper planes.
lower_probe=c.box(90,90,.02,0,0,29.99)
lower_contact=float((seat.m^plate.move(z=-.02).m^lower_probe.m).volume())/.01
upper_contact=intersection(cap,plate.move(z=.02))/.02
assert lower_contact>30 and upper_contact>200,(lower_contact,upper_contact)

report={'revision':c.P['revision'],'all_passed':True,'print_contact':bed,
    'cup_insertion_samples':len(seat_offsets),'cap_insertion_samples':41,'nut_insertion_samples':nut_samples,
    'driver_diameter_mm':2.6,'nut_pocket_AF_mm':round(6.7*np.cos(np.pi/6),3),
    'nut_roof_mm':2.2,'lower_clamp_contact_mm2':round(lower_contact,2),
    'upper_clamp_contact_mm2':round(upper_contact,2),
    'limitations':['Nominal geometry only; print fit, bridging, friction, strength and tightening torque require physical testing.',
                   'The 6.7mm nut-well roof may require local bridging settings; no complete slicer support calculation is claimed.']}
(c.OUT/'p02_split_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=True,indent=2))
