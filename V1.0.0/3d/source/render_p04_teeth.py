"""Show the repaired full gear and the reported tooth notch at equal scale."""
from pathlib import Path
import numpy as np
import build_cad as c

part=next(p for p in c.parts if p.id=='P04B')
printed=part.shape.rot(*part.print_rot)
minimum=np.asarray(printed.m.bounding_box()[:3])
printed=printed.move(*(-minimum))
before_file=c.ROOT/'.build/P04B_before.stl'
if before_file.exists():
    mesh=c.trimesh.load_mesh(before_file,process=True)
    before=c.S(c.mf.Manifold(c.mf.Mesh(np.asarray(mesh.vertices,dtype=np.float32),
                                     np.asarray(mesh.faces,dtype=np.uint32))), '')
    reference='修正前STL'
else:
    # Keep the comparison reproducible without distributing the defective STL.
    damaged=part.shape-c.nut(-33,-19,41,1)-c.hole(-33,-19,41,1)
    before=damaged.rot(*part.print_rot).move(*(-minimum))
    reference='依原誤切孔槽重建的缺口示意'

camera=np.asarray((-1.2,.7,.8));camera/=np.linalg.norm(camera)
right=np.cross([0,0,1.],camera);right/=np.linalg.norm(right)
def panel(shape,origin,offset,factor=1):
    result=shape.move(*(-np.asarray(origin)))
    if factor!=1:result=c.S(result.m.scale((factor,)*3),f'scale({factor}){{{result.code}}}')
    return result.move(*(right*offset))
def point(position,origin,offset,factor=1):
    return tuple((np.asarray(position)-np.asarray(origin))*factor+right*offset)

whole_origin=(37.2,37.2,11)
detail_origin=(5.3,55.8,3.75)
crop=c.box(15,15,7.7,5.3,55.8,-.1)
items=[(panel(printed,whole_origin,-145),(96,134,152)),
       (panel(before&crop,detail_origin,0,5),(218,130,83)),
       (panel(printed&crop,detail_origin,145,5),(93,153,137))]
c.render('P04B_完整60齒檢查.png',items=items,origin_mm=(0,0,0),scale_px_mm=3.7,
         camvec=tuple(camera),headline='P04B 齒面修復：完整60齒，齒輪厚度7.5mm',
         subline='左：修復後實際P04B　中：'+reference+'局部　右：修復後相同位置；局部皆放大5倍',
         notes=['原承載盤孔槽曾切到210°附近的一齒，在Z41至42mm留下缺口；現在P04B獨立建模，排除此誤切。',
                '完整60齒全厚度的逐齒檢查見p04_split_validation.json；7.5mm齒厚、2mm間隙與原四組M3×8保持。',
                '本次只重印P04B，已延長的P26及其他39種STL沿用；齒形與尺寸仍需實印試配。'],
         annotations=[('修復後P04B',point((37.2,37.2,29),whole_origin,-145),(90,270)),
                      ('修正前：齒面中段被挖空',point((5,55.8,2),detail_origin,0,5),(650,270)),
                      ('修復後：全厚度齒形連續',point((5,55.8,2),detail_origin,145,5),(1250,1030))])
