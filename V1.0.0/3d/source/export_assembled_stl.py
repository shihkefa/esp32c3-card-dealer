"""Export the current assembled machine to one millimetre-scale STL.

Uses the assembly coordinates, not the separate bed-oriented STLs. Purchased
hardware is an approximate reference model. Cards, optional weights, narrow-card
spacers and the test coupon are excluded from the standard unloaded assembly.
"""
import json
from pathlib import Path
import build_cad as cad
import numpy as np

members=[(pid,name,shape) for pid,name,shape,_ in cad.assembly_printables()]
members.extend((name,name,shape) for name,shape,_ in cad.hardware if name not in {'cards','cardedge'})

source_meshes=[cad.tm(shape) for _,_,shape in members]
assert all(m.is_watertight and m.volume>0 for m in source_meshes)
# An assembly is a collection of parts, not a boolean-fused printable body.
# Keep the component surfaces and their original positions in one STL file.
mesh=cad.trimesh.util.concatenate(source_meshes)
assert mesh.is_watertight and mesh.volume>0
assert np.isfinite(mesh.vertices).all()
# Preserve the assembly origin in XY and place its lowest face on the bed plane.
mesh.apply_translation([0,0,-mesh.bounds[0,2]])
target=cad.OUT.parent/f"發牌機_整機組裝_{cad.P['revision']}.stl"
mesh.export(target,file_type='stl')
loaded=cad.trimesh.load_mesh(target,process=False)
assert len(loaded.faces)>0 and loaded.volume>0
assert len(loaded.faces)==sum(len(m.faces) for m in source_meshes)
assert np.allclose(loaded.bounds,mesh.bounds,atol=0.001)
cursor=0
roundtrip_parts=[]
for (pid,name,_),original in zip(members,source_meshes):
    count=len(original.faces)
    triangles=loaded.triangles[cursor:cursor+count]
    part=cad.trimesh.Trimesh(vertices=triangles.reshape(-1,3),faces=np.arange(count*3).reshape(-1,3),process=True)
    assert part.is_watertight and part.volume>0,(pid,name)
    roundtrip_parts.append({'id':pid,'name':name,'triangles':count,'closed':True})
    cursor+=count
report={
    'file':str(target),'units':'mm','purpose':'assembly preview; not a print-in-place design',
    'printed_instances':sum(1 for _ in cad.assembly_printables()),
    'hardware_reference_instances':len(members)-sum(1 for _ in cad.assembly_printables()),
    'excluded':['cards','optional P10/P11 weights','optional P12 narrow-card spacers','P30 fit coupon'],
    'triangles':len(loaded.faces),'dimensions_mm':loaded.extents.round(2).tolist(),
    'all_component_shells_closed':True,'bytes':target.stat().st_size,
    'note':'Individual closed shells can touch; do not fuse or print this as a working mechanism.',
    'components':roundtrip_parts,
}
target.with_suffix('.verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='components'},ensure_ascii=False,indent=2))
