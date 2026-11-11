"""Exhaustive pair audit of the modeled assembly, plus movement samples.

Checks the CAD/reference envelopes, not unknown physical component variants.
Every pair is classified; deliberate thread engagement/rubber preload is logged.
"""
import json,math,time
from dataclasses import dataclass
from itertools import combinations
import numpy as np
import build_cad as c

@dataclass
class Actor:
    key:str
    kind:str
    shape:object
    group:str
    def __post_init__(self):self.bounds=np.array(self.shape.m.bounding_box())
    def bbox(self):return self.bounds

fixed_hw={'6005ZZ','28BYJ-48','slipring_flange','batteryholder','18650','ESP32C3','charger','TypeC','booster','protection1S','ULN2003','powerrocker','home_opto','slipM3x8','slipM3nut','baseM3x25','baseM3nut','retainerM3x8','retainerM3nut','stepperM3x8','stepperM3nut','homeM3x8'}
fixed_print={'P01','P02A','P02B','P03','P25','P29','P36'}
def actors():
    a=[];counts={}
    for pid,_,shape,_ in c.assembly_printables():
        counts[pid]=counts.get(pid,0)+1
        group='fixed' if pid in fixed_print else 'pinion' if pid in {'P05A','P05B'} else 'rotating'
        a.append(Actor(f'{pid}.{counts[pid]}',pid,shape,group))
    for name,shape,_ in c.hardware:
        if name=='cardedge':continue
        counts[name]=counts.get(name,0)+1
        group='fixed' if name in fixed_hw else 'pinion' if name in {'pinionM3x8','pinionM3nut','pinionJoinM3x8','pinionJoinM3nut','stepper_output'} else 'rotating'
        a.append(Actor(f'{name}.{counts[name]}',name,shape,group))
    return a

THREADS={
 'hatchM3x8':{'P32B'},'frontM3x8':{'P32A'},'keysM3x8':{'P32A'},'oledM3x8':{'P32A'},
 'n20clampM3x8':{'P18'},'guideM3x8':{'P13','P14'},
 'adjustM3x8':{'P13','P14'},
 'homeM3x8':{'P02A'},
}
def reason(a,b,volume):
    # A bounded exception for modeled smooth screw major diameters in minor-
    # diameter printed pilot holes; not a blanket exemption of whole parts.
    if volume<16 and (b.kind in THREADS.get(a.kind,set()) or a.kind in THREADS.get(b.kind,set())):return 'designed screw/pilot thread engagement (<16mm3 per pair)'
    if a.kind==b.kind=='silicone' and volume<4:return 'elastic roller-ring preload (bounded <4mm3; compression up to 0.45mm in adjustment test)'
    if {a.kind,b.kind}<={'feedrubber','cards','moving_card'} and volume<15:return 'elastic feed-ring contact with card (<15mm3)'
    if {a.kind,b.kind}<={'silicone','cards','moving_card'} and volume<15:return 'elastic outlet-ring contact with card (<15mm3)'
    return None

def overlap(a,b):
    aa=a.bbox();bb=b.bbox()
    if np.any(np.minimum(aa[3:],bb[3:])-np.maximum(aa[:3],bb[:3])<=1e-6):return 0.0,False,None
    hit=a.shape.m^b.shape.m
    vol=float(hit.volume())
    return round(vol,6),True,list(hit.bounding_box()) if vol>.02 else None

def audit_pair(a,b):
    volume,candidate,bounds=overlap(a,b)
    why=reason(a,b,volume) if volume>.02 else None
    return {'a':a.key,'b':b.key,'candidate':candidate,'volume_mm3':volume,'classification':'unexpected' if volume>.02 and not why else 'intended' if why else 'clear','reason':why,'intersection_bounds_mm':bounds}

def moved(a,shape):return Actor(a.key,a.kind,shape,a.group)
def translate_local(a,dz=0,dy=0,dx=0):
    t=math.radians(c.P['hopper_tilt_deg'])
    return moved(a,a.shape.move(math.cos(t)*dx+math.sin(t)*dz,dy,-math.sin(t)*dx+math.cos(t)*dz))

class Motion:
    def __init__(self,name,notes):
        self.data={'test':name,'notes':notes,'poses':0,'classified_pairs':0,'exact_candidates':0,'unexpected':{},'intended':{}}
    def cross(self,left,right,pose):
        self.data['poses']+=1;self.data['classified_pairs']+=len(left)*len(right)
        if not left or not right:return
        la=np.array([a.bbox() for a in left]);rb=np.array([b.bbox() for b in right])
        mask=np.all(np.minimum(la[:,None,3:],rb[None,:,3:])-np.maximum(la[:,None,:3],rb[None,:,:3])>1e-6,axis=2)
        for i,j in np.argwhere(mask):
            a,b=left[i],right[j];result=audit_pair(a,b);self.data['exact_candidates']+=1
            cl=result['classification']
            if cl!='clear':
                key=' / '.join(sorted([a.key,b.key]));old=self.data[cl].get(key)
                if old is None or result['volume_mm3']>old['volume_mm3']:
                    self.data[cl][key]={**result,'pose':pose}
    def finish(self):
        self.data['unexpected']=list(self.data['unexpected'].values());self.data['intended']=list(self.data['intended'].values())
        self.data['passed']=not self.data['unexpected'];return self.data

def run():
    started=time.time();allactors=actors();bykey={a.key:a for a in allactors};parts={p.id:p for p in c.parts}
    static=[audit_pair(a,b) for a,b in combinations(allactors,2)]
    unexpected=[x for x in static if x['classification']=='unexpected']
    print('Static: '+str(len(static))+' pairs; unexpected '+str(len(unexpected)),flush=True)
    tests=[]
    # Internal pairs in a rigid group are invariant and covered by the exhaustive
    # static matrix. All pairs across relative-motion groups are reclassified.
    yaw=Motion('360-degree yaw / conjugate gears','360 samples at 1 degree; pinion angle=-2*yaw. Internal rigid-group pairs use the static matrix. Sampling does not prove a continuous sweep.')
    fixed=[a for a in allactors if a.group=='fixed'];rot=[a for a in allactors if a.group=='rotating'];pin=[a for a in allactors if a.group=='pinion']
    for deg in range(360):
        rr=[moved(a,a.shape.rot(z=deg)) for a in rot]
        pp=[moved(a,a.shape.move(x=-54).rot(z=-2*deg).move(x=54)) for a in pin]
        yaw.cross(rr+pp,fixed,{'yaw_deg':deg});yaw.cross(rr,pp,{'yaw_deg':deg})
    tests.append(yaw.finish());print('Yaw complete: '+str(len(tests[-1]['unexpected']))+' unexpected pairs',flush=True)

    button=Motion('top key travel','Four caps tested 0/0.10/0.20/0.35mm downward. Switch plunger is shortened by the same displacement; 0.05mm nominal cap seating gap.')
    for i,y in enumerate([4,17,30,43],1):
        changing={f'P27.{i}',f'keyplunger.{i}'}
        for d in [0,.1,.2,.35]:
            cap=moved(bykey[f'P27.{i}'],bykey[f'P27.{i}'].shape.move(z=-d))
            plunger=Actor(f'keyplunger.{i}','keyplunger',c.head_pose(c.cyl(2.8,6-d,75,y,121.5)),'rotating')
            button.cross([cap,plunger],[a for a in allactors if a.key not in changing],{'key':i,'stroke_mm':d})
            button.cross([cap],[plunger],{'key':i,'stroke_mm':d})
    tests.append(button.finish())

    carriage=Motion('upper roller adjustment','Local vertical offset -0.30 to +0.80mm in 0.10mm steps; upper wheel, bearings, blocks, screw and shaft move together. Rubber preload is bounded and logged.')
    keys={'P15.1','P15.2','P16.2','upper623.1','upper623.2','upper3mmshaft.1','silicone.3','silicone.4','adjustM3x8.1','adjustM3x8.2','wheelM3x8.2','wheelM3nut.2'}
    for d in np.round(np.arange(-.3,.801,.1),2):
        carriage.cross([translate_local(a,dz=float(d)) for a in allactors if a.key in keys],[a for a in allactors if a.key not in keys],{'local_z_offset_mm':float(d)})
    tests.append(carriage.finish())

    gate=Motion('separator gap adjustment','Gate bottom clearance 0.35 / 0.45 / 0.60mm over local card floor. Fixed screw axis at Z72 travels in recessed elongated slot.')
    for d in [-.1,0,.15]:gate.cross([translate_local(a,dz=d) for a in allactors if a.kind in {'P09','separatorpad'}],[a for a in allactors if a.kind not in {'P09','separatorpad'}],{'gap_mm':round(.45+d,2)})
    tests.append(gate.finish())

    def variant(width,length,count=108,weights=False):
        result=[]
        for a in allactors:
            if a.kind=='cards':continue
            if width==57 and a.kind in {'P24','exit_opto'}:a=translate_local(a,dy=-1.5)
            result.append(a)
        result.append(Actor('cards.variant','cards',c.inclined_head_pose(c.box(length,width,count*.3,44.5-length/2,0,64)),'rotating'))
        if width==57:
            for side in [0,1]:
                s=parts['P12'].shape
                if side:s=s.rot(z=180).move(x=-8)
                result.append(Actor(f'P12.{side+1}','P12',c.assembly_pose('P12',s),'rotating'))
        if weights:
            for pid in ['P10','P11']:result.append(Actor(pid+'.optional',pid,c.assembly_pose(pid,parts[pid].shape.move(z=64+count*.3-97)),'rotating'))
        return result
    optional=Motion('both card sizes and descending optional weight','57x87 with two P12 spacers and exit sensor shifted inward 1.5mm; 60x96 without spacers. Weight positions for 1/13/54/108 cards at reference thickness 0.30mm.')
    for w,l in [(57,87),(60,96)]:
        for count in [1,13,54,108]:
            vv=variant(w,l,count,True)
            changed={a.key for a in vv if a.kind in {'P12','P10','P11','cards','P24','exit_opto'}}
            changing=[a for a in vv if a.key in changed];stationary=[a for a in vv if a.key not in changed]
            optional.cross(changing,stationary,{'width':w,'length':l,'count':count})
            for a,b in combinations(changing,2):optional.cross([a],[b],{'width':w,'length':l,'count':count})
    tests.append(optional.finish())

    path=Motion('single card through feed path','One 0.30mm card translated along inclined local X by 0..150mm in 2mm steps for both sizes. Rigid card path only; no ballistic flight, bending, double-feed or friction simulation.')
    for w,l in [(57,87),(60,96)]:
        environment=[a for a in variant(w,l) if a.kind!='cards']
        for d in range(0,151,2):
            card=Actor('moving_card','moving_card',c.inclined_head_pose(c.box(l,w,.3,44.5-l/2+d,0,64)),'rotating')
            path.cross([card],environment,{'width':w,'length':l,'advance_mm':d})
    tests.append(path.finish())

    housing=Motion('lower preassembled upper cover over head','UI/PCF/DRV and cover panels preinstalled, three bottom mounting screws fitted afterwards. Shroud lowered vertically from +80mm in 2mm steps. Deck is unloaded and optional weights absent.')
    hoodkinds={'P27','P28','P32A','P32B','P33','P34','P35','screenpcb','OLEDglass','screenheader','keypcb','keybody','keyplunger','PCF8574','DRV8833','hatchM3x8','frontM3x8','oledM3x8','keysM3x8','hoodM3nut','hoodJoinM3x8','hoodJoinM3nut'}
    moving=[a for a in allactors if a.kind in hoodkinds];stationary=[a for a in allactors if a.kind not in hoodkinds|{'cards','hoodM3x8'}]
    for d in range(80,-1,-2):housing.cross([moved(a,a.shape.move(z=d)) for a in moving],stationary,{'height_above_final_mm':d})
    tests.append(housing.finish())

    hatch=Motion('side service hatch insertion','Hatch approaches along +Y from 20mm outside. Four hatch screws installed after seating; no card stack loaded.')
    for d in range(-20,1):hatch.cross([moved(bykey['P33.1'],bykey['P33.1'].shape.move(y=d))],[a for a in allactors if a.kind not in {'P33','hatchM3x8','cards'}],{'y_offset_mm':d})
    tests.append(hatch.finish())

    shaft=Motion('journal and collar subassembly','Preassembled P04A/P04B with four deck screws/nuts lowered through P02A/P02B/P03/6005 before collar/base installed. P06 with captured nut but without radial screw then slides UP onto exposed journal from below; collar cannot snap sideways over shaft.')
    bearing=[a for a in allactors if a.kind in {'P02A','P02B','P03','6005ZZ','retainerM3x8','retainerM3nut'}]
    deck=[a for a in allactors if a.kind in {'P04A','P04B','deckM3x8','deckM3nut'}]
    for d in range(30,-1,-1):shaft.cross([moved(a,a.shape.move(z=d)) for a in deck],bearing,{'step':'journal down','z_offset_mm':d})
    collar=[a for a in allactors if a.kind in {'P06','rotorM3nut'}]
    for d in range(-20,1):shaft.cross([moved(a,a.shape.move(z=d)) for a in collar],bearing+deck,{'step':'collar up before base','z_offset_mm':d})
    tests.append(shaft.finish())

    roller=Motion('roller/pedestal subassembly','Pedestals with bearings and upper blocks slide onto shafts from OUTSIDE along Y before fixing to P31; P22 coupling, RF motor, guide and housing fitted later. Only that declared subassembly is checked for insertion.')
    rollerfixed=[a for a in allactors if a.kind in {'P16','lower3mmshaft','upper3mmshaft','silicone','wheelM3x8','wheelM3nut'}]
    for i,side in [(1,-1),(2,1)]:
        ks={f'P{12+i:02}.1',f'P15.{i}',f'lower623.{i}',f'upper623.{i}',f'adjustM3x8.{i}'}
        moving=[a for a in allactors if a.key in ks]
        for d in range(12,-1,-1):roller.cross([translate_local(a,dy=side*d) for a in moving],rollerfixed,{'side':side,'outward_offset_mm':d})
    tests.append(roller.finish())

    spinning=Motion('split hubs and clamp screws rotate','Four drive groups, every 5 degrees. Clamp screws/nuts rotate with their hub. Slots and clamp forces are not a deformation/torque proof.')
    def spin(a,cx,cz,deg):
        # Undo the global head lift before undoing the inclined deck pose.
        # Otherwise the lift is incorrectly rotated into a local X offset.
        raw=a.shape.move(z=-(c.P['card_floor_z_mm']+c.P['hopper_lift_mm']+c.UPPER_LIFT)).rot(y=-c.P['hopper_tilt_deg']).move(z=c.P['card_floor_z_mm'])
        raw=raw.move(x=-cx,z=-cz).rot(y=deg).move(x=cx,z=cz)
        return moved(a,c.inclined_head_pose(raw))
    for label,cx,cz,ks in [
        ('lower roller',61,54.2,{'P16.1','wheelM3x8.1','wheelM3nut.1','silicone.1','silicone.2'}),
        ('upper roller',61,74.75,{'P16.2','wheelM3x8.2','wheelM3nut.2','silicone.3','silicone.4'}),
        ('feed wheel',-22,54,{'P17.1','feedM3x8.1','feedM3nut.1','feedrubber.1','feedrubber.2'}),
        ('coupling',61,54.2,{'P22.1','couplerM3x8.1','couplerM3x8.2','couplerM3nut.1','couplerM3nut.2'}),
    ]:
        for deg in range(0,360,5):spinning.cross([spin(a,cx,cz,deg) for a in allactors if a.key in ks],[a for a in allactors if a.key not in ks],{'group':label,'angle_deg':deg})
    tests.append(spinning.finish())

    lower=Motion('upper unit to base before underside slip-ring screws','Flange and three P36 clips/captive nuts prelocated as upper unit. Lower vertically by 60mm in 2mm steps; slip M3x8, stepper and base fastening screws installed afterwards. Pegs are reference flange locators, not M2 screws.')
    base_kinds={'P01','P29','batteryholder','18650','ESP32C3','charger','TypeC','booster','protection1S','ULN2003','powerrocker','baseM3nut','stepperM3nut'}
    last={'slipM3x8','baseM3x25','stepperM3x8','cards'}
    for d in range(60,-1,-2):
        lower.cross([moved(a,a.shape.move(z=d)) for a in allactors if a.kind not in base_kinds|last],[a for a in allactors if a.kind in base_kinds],{'height_above_final_mm':d})
    tests.append(lower.finish())

    tools=Motion('roller adjustment tool access','P33 and its screws removed. A reserved 3mm-diameter L-tool with 12mm short leg enters along +Y. Longer ordinary hex keys are not certified to fit; adjust before fitting cover if needed.')
    for yy in [-35,35]:
        tool=c.inclined_head_pose(c.cyl(3,12,61,yy,88.9)+c.cyly(3,yy+102,61,-102,100.9))
        for d in range(-30,1,2):tools.cross([Actor('tool.L12','tool',tool.move(y=d),'access')],[a for a in allactors if a.kind not in {'P33','hatchM3x8'}],{'target_local_y':yy,'y_offset_mm':d})
    tests.append(tools.finish())

    usb=Motion('USB Type-C plug insertion','Reference 10mm-wide x6mm-high molded plug body stays outside X=-83; 6.7x2.6mm metal tip protrudes 3.3mm. TypeC receptacle solid excluded as the intended mating envelope.')
    plug=c.box(12,10,6,-89,-36.5,8.3)+c.box(3.3,6.7,2.6,-81.35,-36.5,10)
    for d in range(-20,1):usb.cross([Actor('usb.plug','plug',plug.move(x=d),'access')],[a for a in allactors if a.kind!='TypeC'],{'x_offset_mm':d})
    tests.append(usb.finish())

    report={'revision':c.P['revision'],'scope':'CAD/reference-envelope virtual assembly; not physical trial assembly','tolerance_mm3':.02,'actors':[{'key':a.key,'kind':a.kind,'group':a.group,'bbox_mm':a.bbox().tolist()} for a in allactors],'static_pairs':static,'motion_tests':tests,'limitations':['1-degree yaw and discrete insertion/travel samples are not a continuous swept-volume proof.','PCB solder, terminals, exact switch stroke, cell model, purchased-part tolerances and flexible wire harness are not fully specified.','No physical printing, slicer/support validation, feeding-speed, force/friction, durability or electrical test performed.']}
    summary={'actors':len(allactors),'static_pairs':len(static),'static_candidate_pairs':sum(x['candidate'] for x in static),'static_intended_pairs':sum(x['classification']=='intended' for x in static),'static_unexpected':unexpected,'motion_pose_checks':sum(t['poses'] for t in tests),'motion_classified_pairs':sum(t['classified_pairs'] for t in tests),'motion_exact_candidates':sum(t['exact_candidates'] for t in tests),'motion_unexpected':[{'test':t['test'],**x} for t in tests for x in t['unexpected']],'all_passed':not unexpected and all(t['passed'] for t in tests),'elapsed_s':round(time.time()-started,1)}
    report['summary']=summary
    (c.OUT/'virtual_assembly_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=='__main__':run()
