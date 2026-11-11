"""Check the centered split upper housing and its internal M3 joints.

The checks concern nominal solids and sampled subassembly paths. They do not
establish printed tolerances, tightening torque, preload or fatigue strength.
"""
import hashlib,io,json,math
from pathlib import Path
import numpy as np
import build_cad as c

parts={p.id:p for p in c.parts}
a,b=parts['P32A'].shape,parts['P32B'].shape
hardware={}
for name,shape,_ in c.hardware:
    # This housing-only bench check uses native part coordinates. Its mounted
    # height changes with P04B, while the printable housing remains unchanged.
    native=shape.move(z=-c.UPPER_LIFT) if name in c.RAISED_HARDWARE else shape
    hardware.setdefault(name,[]).append(native)
screws=hardware['hoodJoinM3x8'];nuts=hardware['hoodJoinM3nut']
checks=[]
def vol(s):return float(s.m.volume())
def hit(x,y):return vol(x&y)
def record(name,passed,**details):checks.append({'test':name,'passed':bool(passed),**details})
def path(moving,obstacles,axis,distances):
    worst=0.;first=None;count=0
    for distance in distances:
        posed=moving.move(**{axis:float(distance)})
        overlap=max([hit(posed,o) for o in obstacles] or [0])
        if overlap>.001 and first is None:first=float(distance)
        worst=max(worst,overlap);count+=1
    return {'samples':count,'maximum_overlap_mm3':round(worst,8),
            'first_blocked_offset_mm':None if first is None else round(first,5)}

mesh_checks=[];bed=[]
for pid,minimum,roof_top in [('P32A',5000,c.P32_A_ROOF_TOP_Z),('P32B',2500,c.P32_B_ROOF_TOP_Z)]:
    p=parts[pid];shape=p.shape
    source=c.tm(shape)
    roundtrip=c.trimesh.load_mesh(io.BytesIO(source.export(file_type='stl')),file_type='stl')
    printed=shape.rot(*p.print_rot);bounds=np.asarray(printed.m.bounding_box())
    dims=bounds[3:]-bounds[:3]
    slab=c.box(float(dims[0]+2),float(dims[1]+2),.02,
        float((bounds[0]+bounds[3])/2),float((bounds[1]+bounds[4])/2),float(bounds[2]))
    area=hit(printed,slab)/.02
    good=source.is_watertight and roundtrip.is_watertight and source.volume>0 and len(shape.m.decompose())==1
    good=good and np.all(dims<=np.array([175,175,180]))
    mesh_checks.append({'part':pid,'watertight_after_STL_roundtrip':bool(roundtrip.is_watertight),
        'connected_bodies':len(shape.m.decompose()),'print_dimensions_mm':dims.round(4).tolist(),'passed':bool(good)})
    bed.append({'part':pid,'contact_area_mm2':round(area,3),'source_bed_z_mm':round(float(bounds[2]),4),
        'minimum_mm2':minimum,'passed':bool(area>=minimum and abs(bounds[2]+roof_top)<1e-5)})
record('Both split housing parts are closed single bodies within A1 mini safe bounds',
       all(x['passed'] for x in mesh_checks),parts=mesh_checks)
record('Both housing parts print on their own large planar roof faces',
       all(x['passed'] for x in bed),sampled_first_layer_mm=.02,parts=bed,
       warning='Local nut-slot and hole bridging still needs slicing; not a support-free claim.')

combined=a+b+parts['P33'].shape+parts['P34'].shape
bounds=np.asarray(combined.m.bounding_box())
center_y=(bounds[1]+bounds[4])/2
record('Front-view upper housing envelope is centered on the fixed rotation axis',
       abs(center_y)<.00001 and abs(bounds[4]-98.2)<.00001 and abs(bounds[1]+98.2)<.00001,
       assembled_y_interval_mm=[round(float(bounds[1]),4),round(float(bounds[4]),4)],
       assembled_width_mm=round(float(bounds[4]-bounds[1]),4),center_y_mm=round(float(center_y),8),
       unchanged_X_extent_of_P32_mm=[-73,101],
       scope='Front-view transverse centering only. Existing X-direction control/outlet projection remains.')

ab_overlap=hit(a,b)
body_fastener_overlap=[]
for i,(s,n) in enumerate(zip(screws,nuts),1):
    body_fastener_overlap.append({'joint':i,'maximum_overlap_mm3':round(max(hit(s,a),hit(s,b),hit(n,a),hit(n,b),hit(s,n)),8)})
record('Housing halves and seated new fasteners have no unintended solid overlap',
       ab_overlap<.001 and all(x['maximum_overlap_mm3']<.001 for x in body_fastener_overlap),
       halves_overlap_mm3=round(ab_overlap,8),joints=body_fastener_overlap)

seam_samples=[]
for x in (-35,0,40,80):
    gap=c.box(.1,.16,.3,x,c.P32_SEAM_Y,126.7)
    seam_samples.append({'x_mm':x,'gap_overlap_mm3':round(max(hit(gap,a),hit(gap,b)),8)})
record('Hidden original split retains 0.2mm clearance under the external cover lip',
       all(x['gap_overlap_mm3']<.000001 for x in seam_samples)
       and abs(c.P32_SEAM_Y+55)<1e-8,
       seam_y_mm=c.P32_SEAM_Y,nominal_gap_mm=c.P32_SEAM_GAP,samples=seam_samples,
       closest_existing_front_cover_mount_y_mm=-44,
       retained_housing_mounts_mm=c.HOUSING_MOUNTS,retained_oled_mounts_mm=c.OLED_MOUNTS,
       retained_key_mounts_mm=c.KEY_MOUNTS)

# The visible shoulder is an actual change of roof and side planes. The
# original split line stays underneath the 6.1mm-long U-shaped cover skin.
lap_samples=[]
for xx in (-56,-18,20,64,90):
    for yy in (-60.7,-58,-55.2):
        q=c.box(.1,.1,.9,xx,yy,127.65)
        lap_samples.append({'surface':'roof','x_mm':xx,'y_mm':yy,'solid_ratio':round(hit(q,a)/vol(q),8)})
for xx in (-72.4,100.4):
    for yy in (-60.7,-58,-55.2):
        for zz in (50,80,120):
            q=c.box(.1,.1,.1,xx,yy,zz)
            lap_samples.append({'surface':'side','x_mm':xx,'y_mm':yy,'z_mm':zz,
                                'solid_ratio':round(hit(q,a)/vol(q),8)})
record('A covers the roof and both side faces without growing the outer X envelope',
       all(s['solid_ratio']>.995 for s in lap_samples)
       and abs(a.m.bounding_box()[0]+73)<1e-8 and abs(a.m.bounding_box()[3]-101)<1e-8,
       cover_end_y_mm=c.P32_LAP_END_Y,cover_length_from_original_edge_mm=6.1,
       nominal_skin_thickness_mm=c.P32_LAP_SKIN,samples=lap_samples)

clearances=[]
for xx in (-56,-18,20,64):
    for yy in (-60.7,-58,-55.2):
        q=c.box(.1,.1,.2,xx,yy,127.25)
        clearances.append({'surface':'roof','x_mm':xx,'y_mm':yy,
            'maximum_overlap_mm3':round(max(hit(q,a),hit(q,b)),8)})
for xx in (-71.65,99.65):
    for yy in (-60.7,-58,-55.2):
        for zz in (50,80,120):
            q=c.box(.2,.1,.1,xx,yy,zz)
            clearances.append({'surface':'side','x_mm':xx,'y_mm':yy,'z_mm':zz,
                'maximum_overlap_mm3':round(max(hit(q,a),hit(q,b)),8)})
record('Covered roof and side rebates retain 0.3mm nominal assembly clearance',
       abs(c.P32_B_SETBACK-c.P32_LAP_SKIN-c.P32_LAP_CLEARANCE)<1e-8
       and all(s['maximum_overlap_mm3']<.000001 for s in clearances),
       nominal_gap_mm=c.P32_LAP_CLEARANCE,samples=clearances,
       warning='Nominal CAD allowance only; elephant foot and material shrinkage require trial fitting.')

wall_samples=[]
for xx in (-70.4,98.4):
    for yy in (-66,-72):
        q=c.box(2.1,.1,.1,xx,yy,80)
        wall_samples.append({'surface':'side','x_mm':xx,'y_mm':yy,'solid_ratio':round(hit(q,b)/vol(q),8)})
for xx,yy in [(0,-70),(0,-80),(40,-70)]:
    q=c.box(.1,.1,2.1,xx,yy,125.05)
    wall_samples.append({'surface':'roof','x_mm':xx,'y_mm':yy,'solid_ratio':round(hit(q,b)/vol(q),8)})
step_voids=[]
for xx in (-72.4,100.4):
    q=c.box(.1,.1,.1,xx,-62,80)
    step_voids.append(round(max(hit(q,a),hit(q,b)),8))
q=c.box(.1,.1,.1,0,-62,128.0)
step_voids.append(round(max(hit(q,a),hit(q,b)),8))
record('B retains 2.2mm roof and side walls behind an intentional 1.5mm visible step',
       all(s['solid_ratio']>.995 for s in wall_samples)
       and max(step_voids)<.000001
       and abs(b.m.bounding_box()[5]-127.2)<1e-5 and abs(b.m.bounding_box()[2]-43)<1e-5,
       B_roof_outer_mm=c.P32_B_ROOF_TOP_Z,B_roof_inner_mm=c.P32_B_ROOF_INNER_Z,
       B_side_outer_mm=c.P32_B_OUTER_X,B_side_inner_mm=c.P32_B_INNER_X,
       nominal_wall_mm=2.2,nominal_visible_setback_mm=c.P32_B_SETBACK,
       samples=wall_samples,external_step_void_overlap_mm3=step_voids)

p33=parts['P33'].shape
p33_path=path(p33,[a,b],'y',np.linspace(-20,0,81))
record('Unchanged P33 side cover seats without interference under the lower B roof',
       max(hit(p33,a),hit(p33,b))<.001 and p33_path['maximum_overlap_mm3']<.001,
       P33_bbox_mm=list(p33.m.bounding_box()),entry=p33_path,
       scope='P33 remains outside at Y=-98.2 to -96. Z-height overlap does not imply volume overlap; the complete solids and entry path are checked.')

nut_entries=[]
for i,n in enumerate(nuts,1):
    result=path(n,[a,b],'y',np.linspace(20,0,81))
    nut_entries.append({'joint':i,**result})
record('Four standard M3 nuts side-load from positive Y into roofed hex cages',
       all(x['maximum_overlap_mm3']<.001 for x in nut_entries),joints=nut_entries,
       nominal_nut_z_interval_mm=[123.1,125.5],slot_z_interval_mm=[123,125.6],
       scope='Load the nuts before attaching UI or installing the housing on the machine.')

join_entry=path(b,[a]+nuts,'y',np.linspace(-30,0,121))
record('Back housing half slides into the main half with preloaded nuts',
       join_entry['maximum_overlap_mm3']<.001,**join_entry,
       clamp_contact_plane_z_mm=c.HOOD_JOIN_INTERFACE_Z,
       assembly_order='Preload A nuts, slide B from negative Y, then install four screws from below.')

screw_entries=[];coverage=[];tool_checks=[]
for i,((x,y),s) in enumerate(zip(c.HOOD_JOIN_MOUNTS,screws),1):
    result=path(s,[a,b]+nuts,'z',np.linspace(-20,0,81))
    screw_entries.append({'joint':i,**result})
    fill=c.cyl(3,2.4,x,y,c.HOOD_JOIN_NUT_Z)
    coverage.append({'joint':i,'nominal_shank_coverage_ratio':round(hit(fill,s)/vol(fill),8)})
    # The hex bit enters the real socket; the 3mm shaft ends below the head.
    tool=(c.cyl(2.30,1.3,x,y,118.4,n=6)+c.cyl(3,45,x,y,73.4)+c.cyl(12,20,x,y,53.4))
    other_screws=[other for j,other in enumerate(screws) if j!=i-1]
    tool_entry=path(tool,[a,b]+nuts+other_screws+[s],'z',np.linspace(-15,0,61))
    tool_checks.append({'joint':i,**tool_entry})
record('M3x8 screws insert axially upward through full countersunk seats',
       all(x['maximum_overlap_mm3']<.001 for x in screw_entries),joints=screw_entries,
       head_z_mm=c.HOOD_JOIN_HEAD_Z,tip_z_mm=c.HOOD_JOIN_HEAD_Z+8)
record('All four new M3 nuts have full nominal 2.4mm screw coverage',
       all(x['nominal_shank_coverage_ratio']>.995 for x in coverage),joints=coverage)
record('Straight 2mm hex tool reaches every joint from inside before installing UI',
       all(x['maximum_overlap_mm3']<.001 for x in tool_checks),joints=tool_checks,
       tool_shank_diameter_mm=3,reference_grip_diameter_mm=12,
       scope='Housing-only bench subassembly, before UI, wiring and machine installation; not a hand-access simulation.')

cone=[];guides=[];roof=[]
for i,(x,y) in enumerate(c.HOOD_JOIN_MOUNTS,1):
    worst_cone=1.;worst_guide=1.
    for height in (118.8,119.2,119.6):
        r=3-(height-c.HOOD_JOIN_HEAD_Z)
        for deg in range(0,360,5):
            angle=math.radians(deg)
            q=c.box(.025,.025,.025,x+(r+.035)*math.cos(angle),y+(r+.035)*math.sin(angle),height-.0125)
            worst_cone=min(worst_cone,hit(q,b)/vol(q))
    for height in (120.3,121.1,122.0):
        for deg in range(0,360,10):
            angle=math.radians(deg)
            q=c.box(.025,.025,.025,x+1.76*math.cos(angle),y+1.76*math.sin(angle),height-.0125)
            worst_guide=min(worst_guide,hit(q,b)/vol(q))
    cone.append({'joint':i,'minimum_sampled_solid_ratio':round(worst_cone,8)})
    guides.append({'joint':i,'minimum_sampled_solid_ratio':round(worst_guide,8)})
    nut_roof=c.cyl(6.2,.7,x,y,125.7)-c.cyl(3.6,.9,x,y,125.6)
    cosmetic_roof=c.cyl(6.7,2.15,x,y,126.55)
    roof.append({'joint':i,'nut_roof_solid_ratio':round(hit(nut_roof,a)/vol(nut_roof),8),
                 'cosmetic_roof_solid_ratio':round(hit(cosmetic_roof,a)/vol(cosmetic_roof),8)})
record('Every new screw retains a complete 360 degree countersunk bearing seat',
       all(x['minimum_sampled_solid_ratio']>.995 for x in cone),joints=cone,
       cone_stations=3,angles_per_station=72)
record('Closed screw guide rings remain above the countersinks',
       all(x['minimum_sampled_solid_ratio']>.995 for x in guides),joints=guides,
       guide_stations=3,angles_per_station=36,nominal_hole_diameter_mm=3.4)
record('Nut cages are roofed and no new screw hole breaks the cosmetic roof',
       all(x['nut_roof_solid_ratio']>.995 and x['cosmetic_roof_solid_ratio']>.995 for x in roof),
       joints=roof,nominal_nut_roof_mm=.9,outer_roof_mm=2.2)

nut_turns=[]
for i,((x,y),n) in enumerate(zip(c.HOOD_JOIN_MOUNTS,nuts),1):
    rotations=[]
    for deg in (-45,-30,-15,15,30,45):
        moved=n.move(-x,-y,0).rot(z=deg).move(x,y,0)
        rotations.append({'degrees':deg,'overlap_mm3':round(hit(moved,a),6)})
    nut_turns.append({'joint':i,'rotations':rotations})
record('Hex cage walls resist sampled nut rotation despite the side-loading door',
       all(r['overlap_mm3']>.001 for j in nut_turns for r in j['rotations']),joints=nut_turns,
       warning='Geometric anti-rotation sampling does not measure torque capacity or plastic strength.')

rib_samples=[]
for x,start in [(72,49),(0,52)]:
    for yy in (66,76,86,94):
        z=53.3+(yy-start)*.5
        probe=c.box(1,.2,.2,x,yy,z)
        rib_samples.append({'x_mm':x,'y_mm':yy,'solid_ratio':round(hit(probe,a)/vol(probe),6)})
record('Extended positive-side support webs connect original mounting feet toward the new wall',
       all(x['solid_ratio']>.995 for x in rib_samples),samples=rib_samples,
       new_inner_wall_y_mm=96,unchanged_mount_positions_mm=c.HOUSING_MOUNTS)

counts={length:sum(x['kind']=='screw' and x.get('length_mm')==length for x in c.fastener_registry) for length in (8,25)}
nut_count=sum(x['kind']=='nut' for x in c.fastener_registry)
record('Only the upper shell is split and four existing-spec fastener sets are added',
       'P32' not in parts and len(parts)==40 and counts=={8:61,25:10} and nut_count==52,
       print_types=len(parts),M3x8=counts[8],M3x25=counts[25],M3_nuts=nut_count,
       separate_unchanged_part_bytes_check='Performed by release packaging against the previous complete ZIP.')

report={'revision':c.P['revision'],'all_passed':all(x['passed'] for x in checks),
    'scope':'Nominal CAD support and sampled bench-subassembly paths; not physical qualification.',
    'source_hashes':{'build_cad_py_sha256':hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
                     'check_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    'checks':checks,'limitations':[
        'Physical print tolerance, layer strength, preload, torque, wiring clearance and durability require trial assembly.',
        'Exploded diagrams are illustrative; sampled nominal paths are not continuous or elastic motion proofs.',
        'Join the two shell pieces before mounting UI; this check does not claim in-machine tool access.',
        'The front view is centered. The original X-direction projection and every other printed part remain by design.'
    ]}
(c.OUT/'p32_split_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'all_passed':report['all_passed'],'checks':[{k:v for k,v in row.items() if k in {'test','passed'}} for row in checks],
                  'mesh_checks':mesh_checks,'bed':bed},ensure_ascii=True,indent=2))
if not report['all_passed']:raise SystemExit(1)
