"""Create enlarged geometric depth comparisons for all engraved part IDs."""
import math
import numpy as np
import build_cad as c

TW,TH=400,200
cols=4;rows=math.ceil(len(c.parts)/cols)
atlas=c.Image.new('RGB',(TW*cols,rows*TH+104),(245,245,240))
draw=c.ImageDraw.Draw(atlas)
fontpath='C:/Windows/Fonts/msjh.ttc'
title=c.ImageFont.truetype(fontpath,29)
font=c.ImageFont.truetype(fontpath,17)
small=c.ImageFont.truetype(fontpath,14)
draw.text((25,14),f"{c.P['revision']} — {len(c.parts)} 種列印件凹刻編號核對",font=title,fill=(27,47,54))
draw.text((25,57),'局部放大；深色為模型實際新增的凹刻。按鍵帽以 27 簡碼對照 P27。',font=font,fill=(78,95,103))

def depth_buffer(shape,origin,u,v,n,w,h,scale):
    mesh=c.tm(shape);verts=np.asarray(mesh.vertices)-origin
    screen=np.column_stack([w/2+verts@u*scale,h/2-verts@v*scale])
    depths=verts@n
    buf=np.full((h,w),-np.inf,dtype=np.float64)
    for face in mesh.faces:
        xy=screen[face];depth=depths[face]
        xmin=max(0,int(math.floor(xy[:,0].min())));xmax=min(w-1,int(math.ceil(xy[:,0].max())))
        ymin=max(0,int(math.floor(xy[:,1].min())));ymax=min(h-1,int(math.ceil(xy[:,1].max())))
        if xmax<xmin or ymax<ymin:continue
        x0,y0=xy[0];x1,y1=xy[1];x2,y2=xy[2]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-9:continue
        yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1]
        aa=((y1-y2)*(xx+.5-x2)+(x2-x1)*(yy+.5-y2))/den
        bb=((y2-y0)*(xx+.5-x2)+(x0-x2)*(yy+.5-y2))/den;cc=1-aa-bb
        zz=aa*depth[0]+bb*depth[1]+cc*depth[2]
        current=buf[ymin:ymax+1,xmin:xmax+1]
        mask=(aa>=-1e-6)&(bb>=-1e-6)&(cc>=-1e-6)&(zz>current)
        current[mask]=zz[mask]
    return buf

for i,p in enumerate(c.parts):
    e=p.engraving
    if e['type']=='cylindrical':
        origin=np.array(e['center_mm'])+np.array([e['radius_mm'],0,0]);u=np.array([0,1,0]);v=np.array([0,0,1]);n=np.array([1,0,0])
    elif e['type']=='annular':
        origin=np.array(e['origin_mm']);u=np.array(e['u']);v=np.array(e['v']);n=np.array(e['normal'])
    else:
        origin=np.array(e['origin_mm']);u=np.array(e['u']);v=np.array(e['v']);n=np.array(e['normal'])
    textw=(len(e['text'])*4-1)*e['height_mm']/5
    focus=c.box(textw+3,e['height_mm']+2.4,2.4,z0=-2).basis(u,v,n,origin)
    before=c.S(c.LABEL_BASE_SHAPES[p.id].m^focus.m,'')
    after=c.S(p.shape.m^focus.m,'')
    w,h=TW-28,140;scale=min(280/max(textw,1),85/e['height_mm'])
    old=depth_buffer(before,origin,u,v,n,w,h,scale)
    new=depth_buffer(after,origin,u,v,n,w,h,scale)
    pixels=np.full((h,w,3),(237,237,231),dtype=np.uint8)
    finite=np.isfinite(old)&np.isfinite(new)
    delta=np.zeros((h,w));delta[finite]=old[finite]-new[finite]
    engraved=finite&(delta>.025)
    assert int(engraved.sum())>15,p.id
    pixels[engraved]=(47,69,76)
    x=(i%cols)*TW;y=104+(i//cols)*TH
    atlas.paste(c.Image.fromarray(pixels),(x+14,y+34))
    draw.text((x+14,y+8),p.id+'  '+p.name,font=font,fill=(31,53,61))
    draw.text((x+14,y+177),f"字高 {e['height_mm']} mm / 凹刻 {e['depth_mm']} mm",font=small,fill=(94,108,113))
    draw.line((x+8,y+TH-2,x+TW-8,y+TH-2),fill=(211,217,214),width=1)
atlas.save(c.OUT/'part_numbering_check.png')
print(str(c.OUT/'part_numbering_check.png'))
