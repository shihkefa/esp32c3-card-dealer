"""Validate every exported STL and engraved ID against current CAD source.

Full assembly and motion coverage is in virtual_assembly_check.py, which must
pass separately. This checks the actual exported files, not just source meshes.
"""
import json
import numpy as np
import build_cad as c

out=c.OUT;parts={p.id:p for p in c.parts};meshes=[]
for p in c.parts:
    m=c.trimesh.load_mesh(out/'STL'/f'{p.id}.stl')
    assert m.is_watertight and m.volume>0,p.id
    parent=list(range(len(m.vertices)))
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for tri in m.faces:
        a=root(int(tri[0]))
        for j in tri[1:]:parent[root(int(j))]=a
    assert len({root(i) for i in range(len(parent))})==1,p.id
    assert np.all(m.extents<=np.array([175,175,180])),p.id
    source=c.tm(p.shape.rot(*p.print_rot))
    assert np.allclose(m.extents,source.extents,atol=.001),p.id
    assert abs(m.volume-source.volume)<max(.005,source.volume*.00001),p.id
    assert p.engraving and p.engraving['removed_mm3']>0,p.id
    assert p.engraving['coverage_ratio']>=.88,p.id
    meshes.append({'id':p.id,'watertight':True,'connected_components':1,'matches_current_source':True,'dimensions_mm':m.extents.round(3).tolist(),'label':p.engraving['text']})

def intersection(a,b):return float((a.m^b.m).volume())
for pid,outer,rootd,x,z,height in [('P04B',74.4,69,0,36,c.P04_GEAR_HEIGHT),('P05A',38.4,33,54,34,6)]:
    removed=c.S(c.LABEL_BASE_SHAPES[pid].m-parts[pid].shape.m,'')
    teeth=c.cyl(outer,height,x,0,z)-c.cyl(rootd,height+2,x,0,z-1)
    assert intersection(removed,teeth)<1e-5,pid
for pid,skin in [
    ('P32A',c.box(12,.3,8,-30,98.05,51)),
    ('P32B',c.box(12,.3,8,-55,-95.85,56)),
    ('P33',c.box(12,.3,8,20,-98.05,76.5)),
    ('P34',c.box(.3,12,8,103.05,0,47)),
    ('P27',c.cyl(8.8,.15,75,4,131.15)),
]:
    removed=c.S(c.LABEL_BASE_SHAPES[pid].m-parts[pid].shape.m,'')
    assert intersection(removed,skin)<1e-5,pid
for x,y in [(-52,-45),(-20,-14),(20,18),(52,48),(0,0),(-30,14)]:
    probe=c.box(2,2,.6,x,y,.8)
    assert abs(intersection(probe,parts['P01'].shape)-probe.m.volume())<1e-5,(x,y)
audit=json.loads((out/'virtual_assembly_report.json').read_text(encoding='utf8'))
assert audit['summary']['all_passed'],audit['summary']
assert audit['revision']==c.P['revision']
fasteners=json.loads((out/'fastener_validation.json').read_text(encoding='utf8'))
assert fasteners['all_passed'] and len(fasteners['screw_skus'])==2 and len(fasteners['nut_skus'])==1
report={'revision':c.P['revision'],'status':'exported mesh and modeled virtual assembly passed; no physical or slicer test','stl_count':len(meshes),'meshes':meshes,'all_ids_verified':True,'gear_working_faces_unmarked':True,'selected_cosmetic_faces_unmarked':True,'base_bottom_skin_closed_at_selected_probes':True,'assembly_summary':audit['summary'],'fastener_summary':{k:v for k,v in fasteners.items() if k!='checks'}}
(out/'geometry_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'stl_count':len(meshes),'all_meshes_and_ids_passed':True,'assembly_passed':True},ensure_ascii=False))
