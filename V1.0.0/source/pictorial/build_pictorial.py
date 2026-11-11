"""Pictorial, pin-to-pin wiring with complete routed wires and an offline viewer."""
from pathlib import Path
from dataclasses import dataclass
import importlib.util
import heapq
import itertools
import json
import math
import csv
import re
import hashlib
import subprocess
import zipfile
from html import escape

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'wiring'
TMP=ROOT/'.build/pictorial'
OUT.mkdir(parents=True,exist_ok=True);TMP.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('vector_base',ROOT/'source/wiring/render_helpers.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
Scene=v.Scene
W,H=4400,3400
PITCH=20
INK='#182d40';GRAY='#586d7e';RED='#d3343a';BLACK='#263643';GREEN='#00876e'
COLORS=[RED,BLACK,GREEN,'#1778c5','#7952b3','#d8750c','#995137','#b29300','#0097a9','#cb417e']

@dataclass
class Pin:
    x:float
    y:float
    side:str
    owner:str

class Part:
    def __init__(self,key,x,y,w,h,title,color='#1b6488',view='元件面'):
        self.key,self.x,self.y,self.w,self.h=key,x,y,w,h
        self.title,self.view=title,view
        self.s=Scene(w,h);self.pins={}
        self.s.rect(7,9,w,h,'#d8dfe5','none',12)
        self.s.rect(0,0,w,h,color,'#183346',12,2.5)
        label_width=min(max(w,330),W-x-55)
        self.s.text(0,-65 if key=='ESP' else -24,title,28,INK,True,maxw=label_width)
        lines=[];line=''
        for ch in view:
            if v.pdfmetrics.stringWidth(line+ch,'CJK',21)>label_width:
                lines.append(line);line=''
            line+=ch
        if line:lines.append(line)
        for j,text in enumerate(lines[:2]):
            if j==1 and len(lines)>2:text=text[:-1]+'…'
            self.s.text(0,h+32+j*28,text,21,GRAY)

    def pin(self,name,x,y,side,label=None,white=True):
        self.pins[name]=Pin(self.x+x,self.y+y,side,self.key)
        if self.key.startswith('R') and self.key not in ('RF300',):
            self.s.line([(x,y),(52 if name=='1' else 178,y)],'#a5afb7',5,halo=False)
        elif self.key in ('Q1','Q2'):
            self.s.rect(x-7,y-10,14,20,'#c0c9ce','#f0f3f4',1)
        elif self.key in ('C1','C2','C3','C4'):
            self.s.line([(x,y),(x,155 if self.key in ('C1','C2') else 72)],'#a8b1b8',5,halo=False)
        elif self.key.startswith('SW'):
            self.s.rect(x-9,y-6,18,12,'#c0c9ce','#e4e9ed',1)
        else:
            self.s.add('circle',x=x,y=y,r=12,fill='#c3a553',stroke='#eee0a7')
            self.s.add('circle',x=x,y=y,r=6,fill='#1d252c',stroke='#786a48')
        if label is not None:
            c='white' if white else INK
            if side=='L':self.s.text(x+22,y+7,label,22,c)
            elif side=='R':self.s.text(x-22,y+7,label,22,c,anchor='end')
            elif side=='T':self.s.text(x,y+34,label,20,c,anchor='middle')
            else:self.s.text(x,y-22,label,20,c,anchor='middle')

    def ic(self,x,y,w,h,text=''):
        for j in range(8):
            yy=y+12+j*(h-24)/7
            self.s.rect(x-13,yy-5,13,10,'#bdc7cc','#8c969d',0)
            self.s.rect(x+w,yy-5,13,10,'#bdc7cc','#8c969d',0)
        self.s.rect(x,y,w,h,'#202931','#505b64',5)
        self.s.add('circle',x=x+14,y=y+h-14,r=5,fill='#76838a',stroke='#76838a')
        if text:self.s.text(x+w/2,y+h/2+8,text,23,'#b5bdc6',anchor='middle',maxw=w-16)

    def component(self,x,y,w,h,color='#a99465'):
        self.s.rect(x,y,w,h,color,'#d2c4a4',3)
        self.s.rect(x,y,7,h,'#c3c9cc','none',0)
        self.s.rect(x+w-7,y,7,h,'#c3c9cc','none',0)

    def hole(self,x,y):
        self.s.add('circle',x=x,y=y,r=17,fill='#b9c7d0',stroke='#dbe5eb')
        self.s.add('circle',x=x,y=y,r=10,fill='#f8fafc',stroke='#455768')


def build_parts():
    parts=[]
    def add(p):parts.append(p);return p
    p=add(Part('電池盒',100,330,600,220,'BT1  18650電池盒','#252b31','正極與負極依電池盒標示；使用現有2900mAh電芯'))
    p.s.rect(65,25,465,170,'#5577b2','#778baf',20)
    p.s.rect(60,42,20,135,'#bfc8d2','#e6edf2',4)
    p.s.text(290,125,'18650  2900mAh',32,'white',True,'middle')
    p.s.text(105,132,'-',35,'white');p.s.text(468,132,'+',35,'white')
    p.pin('-',25,155,'L','-');p.pin('+',575,65,'R','+')

    p=add(Part('1S保護板',890,420,760,160,'U1  1S / 5A 長條保護板','#14634d','焊接面朝上：左B-、右B+；中右上P-、下P+'))
    p.s.rect(22,22,112,116,'#c2c9c5','#d5ded5',3)
    p.s.rect(642,22,96,116,'#c2c9c5','#d5ded5',3)
    for j in range(4):
        p.s.line([(145,36+j*25),(480,36+j*25),(535,45+j*20)],'#3b816d',2,halo=False)
    p.pin('B-',70,80,'L','B-');p.pin('B+',690,80,'R','B+')
    p.pin('P-',540,30,'T','P-');p.pin('P+',540,130,'B','P+')
    p.s.text(282,97,'1S  4.2V',26,'white',True,'middle')

    p=add(Part('TP4056',1110,800,500,380,'U2  TP4056 / HW-387 Type-C無保護版','#156187','USB口朝左；只接右邊BAT+/BAT-到保護板P端'))
    p.s.rect(-45,95,190,180,'#c2c8cf','#73808a',18)
    p.s.rect(-40,132,35,105,'#2b333a','#747f88',13)
    p.s.text(55,191,'TYPE-C',20,INK,True,'middle')
    p.ic(260,188,150,110,'TP4056')
    p.component(215,60,35,82,'#2e3033')
    p.s.text(237,45,'PROG',17,'white',anchor='middle')
    for xx in (335,410):p.component(xx,62,25,45,'#b2cbc5')
    p.pin('IN+',30,30,'T','IN+');p.pin('IN-',30,350,'B','IN-')
    p.pin('BAT+/B+',470,30,'R','BAT+');p.pin('BAT-/B-',470,350,'R','BAT-')

    p=add(Part('SW1',580,870,210,175,'SW1  兩腳無燈總開關','#353b40','兩個金屬腳：串在P+與升壓VIN之間'))
    p.s.rect(28,15,154,100,'#12191d','#727f88',16)
    p.s.text(105,55,'I',35,'white',True,'middle');p.s.text(105,97,'O',28,'#8ea2ae',True,'middle')
    p.pin('1',45,155,'B','1');p.pin('2',165,155,'B','2')

    p=add(Part('TPS61088',960,1320,680,420,'U3  TPS61088 黑板四角焊孔款','#26313a','VIN左上、GND左下；VOUT右上、GND右下；選5V檔'))
    p.s.rect(105,48,180,170,'#9b9fa5','#d3d6da',18)
    p.s.text(195,147,'1R0',44,'#666970',True,'middle')
    p.ic(355,255,100,105,'61088')
    for xx in (105,165,225,285,485,545):p.component(xx,300,40,80)
    for j,label in enumerate(('5V','9V','12V','ADJ')):
        xx=345+j*65;p.s.rect(xx,38,28,11,'#b6b9bc','#bec9cc',2)
        p.s.rect(xx,62,28,11,'#b6b9bc','#bec9cc',2)
        p.s.text(xx+14,108,label,19,'white',anchor='middle')
    p.s.line([(352,44),(352,69)],'#f0c86a',9,halo=False)
    p.s.text(527,196,'PWM',20,'white')
    p.pin('IN+',30,30,'L','VIN');p.pin('IN-',30,390,'L','GND')
    p.pin('OUT+',650,30,'R','VOUT');p.pin('OUT-',650,390,'R','GND')

    p=add(Part('JP-ESP5V',640,1810,210,100,'JP-ESP5V  兩針排針＋可拔跳帽','#303c45','接電腦USB前拔掉短路帽；GND不拔'))
    p.s.rect(45,18,120,65,'#151e25','#71828d',5)
    p.pin('1',20,50,'L','1');p.pin('2',190,50,'R','2')
    p.s.line([(55,50),(155,50)],RED,8,halo=False)

    p=add(Part('ESP',280,2120,460,580,'U4  ESP32-C3 SuperMini','#1f343d','元件面朝上、USB向上；本版GPIO20=SCL / GPIO21=SDA'))
    p.s.rect(170,-37,120,88,'#c3ccd3','#788995',12)
    p.s.rect(195,-28,70,18,'#27343d','#475964',9)
    p.ic(150,220,160,140,'ESP32-C3')
    p.s.rect(160,104,52,42,'#a5a39f','#a5a39f',4)
    p.s.rect(268,104,52,42,'#a5a39f','#a5a39f',4)
    p.s.text(230,430,'SuperMini',28,'white',True,'middle')
    p.s.line([(170,470),(300,470),(300,495),(170,495),(170,520),(300,520)],'#a8b37c',5,halo=False)
    for i,(pin,label) in enumerate([('5V','5V'),('GND','GND'),('3V3','3V3'),('GPIO4','4'),('GPIO3','3'),('GPIO2','2'),('GPIO1','1'),('GPIO0','0')]):
        p.pin(pin,20,90+i*60,'L',label)
    for i,n in enumerate((5,6,7,8,9,10,20,21)):
        p.pin('GPIO'+str(n),440,90+i*60,'R',str(n))

    p=add(Part('ULN2003',1110,2240,600,660,'U5  ULN2003 / X113647','#2b775d','元件面；底排IN1起用前四孔；電源右側下兩腳+ / -'))
    for xx in (40,560):
        p.hole(xx,40);p.hole(xx,620)
    for j in range(4):
        xx=130+j*90;p.s.add('circle',x=xx,y=95,r=24,fill='#d1e4d9',stroke='#8db4a2')
        p.s.text(xx,143,'ABCD'[j],22,'white',True,'middle')
    p.s.rect(85,172,365,105,'#eeeae1','#a6aca6',9)
    for j in range(5):p.pin('M'+str(j+1),120+j*70,220,'T',None)
    p.ic(70,330,365,145,'ULN2003AN')
    for j in range(7):p.pin('IN'+str(j+1),105+j*60,562,'B','IN'+str(j+1))
    p.s.rect(500,330,52,100,'#232a2a','#bec7bc',3)
    p.s.text(480,378,'J1',18,'white',anchor='end')
    p.s.line([(524,345),(524,414)],'#dcb648',17,halo=False)
    p.pin('+/VCC',525,466,'R','+');p.pin('GND',525,526,'R','-')

    p=add(Part('28BYJ',1550,3040,300,240,'M1  28BYJ-48 / 5V','#a6b6c1','原5芯插頭整個插入白色座；不拆換原線序'))
    p.s.add('circle',x=150,y=120,r=105,fill='#bac8d2',stroke='#718b9d')
    p.s.add('circle',x=150,y=85,r=32,fill='#bda677',stroke='#e1d8b5')
    p.s.rect(45,180,210,53,'#3189b4','#315d77',6)
    p.s.text(150,148,'28BYJ-48',24,INK,True,'middle')
    for j in range(5):p.pin('M'+str(j+1),280,40+j*40,'R',None)

    p=add(Part('DRV8833',2810,650,600,540,'U6  DRV8833 / HW-627 12腳黑板','#242a2e','焊接面朝上、J2在上；EEP用一條線接本板VCC(5V)'))
    p.s.rect(230,35,60,30,'#bfc4c8','#eceded',3)
    p.s.rect(296,35,60,30,'#bfc4c8','#eceded',3)
    p.s.text(290,105,'J2',24,'white',True,'middle')
    p.s.text(300,304,'DRV8833',34,'#a7b1b7',True,'middle')
    p.s.text(300,485,'HW-627',25,'white',True,'middle')
    for i,name in enumerate(('IN4','IN3','GND','VCC','IN2','IN1')):p.pin(name,35,80+i*75,'L',name)
    for i,name in enumerate(('EEP','OUT1','OUT2','OUT3','OUT4','ULT')):p.pin(name,565,80+i*75,'R',name)

    p=add(Part('N20',3780,740,310,200,'M2  N20 取牌馬達','#b7a369','從後蓋看兩焊片；方向不對，交換這兩線'))
    p.s.rect(8,32,90,136,'#c1bfa8','#c1bfa8',8)
    p.s.rect(80,38,220,123,'#b8c3cb','#8d9ba4',15)
    p.s.rect(-55,84,63,32,'#dadde0','#8e999f',3)
    p.pin('端子1',290,50,'T','1',False);p.pin('端子2',290,150,'B','2',False)
    p.s.text(188,118,'N20',32,INK,True,'middle')
    p=add(Part('RF300',3780,1180,270,270,'M3  RF300 出牌馬達','#c2ccd2','後蓋面朝上，兩個焊片接OUT3/OUT4'))
    p.s.add('circle',x=135,y=135,r=115,fill='#aebdc8',stroke='#637e90')
    p.s.add('circle',x=135,y=135,r=47,fill='#d3d9df',stroke='#8398a5')
    p.pin('端子1',65,225,'B','1',False);p.pin('端子2',205,225,'B','2',False)
    p.s.text(135,95,'RF300',26,INK,True,'middle')

    p=add(Part('PCF',2740,2180,1220,320,'U7  PCF8574T / 9孔IO長條板','#1b668d','背面朝上：P0在左、INT在右。右邊四針由上而下VCC/GND/SDA/SCL'))
    for j,label in enumerate(['P'+str(n) for n in range(8)]+['INT']):
        p.pin(label,350+j*85,35,'T',label)
    for i,label in enumerate(('VCC','GND','SDA','SCL')):
        p.pin(label,1165,95+i*60,'R',label)
        p.s.rect(170,80+i*60,20,20,'#d7c47d','#eee0a7',2)
        p.s.text(205,98+i*60,label,18,'white')
    for j in range(3):
        for k in range(3):p.s.add('circle',x=385+k*50,y=160+j*55,r=8,fill='#c3b56f',stroke='#e9dba1')
    p.s.text(810,230,'PCF8574',42,'#d8e8f2',True,'middle')
    p.s.text(810,280,'A0/A1/A2 帽跨 A 與 - (GND)',23,'white',anchor='middle')
    for j in range(3):
        p.s.line([(385,160+j*55),(485,160+j*55)],'#4586a4',2,halo=False)

    p=add(Part('OLED',3330,2720,640,570,'U8  SSD1306 0.96吋 4針I2C','#256987','正面朝上、排針在上；本指定板由左到右GND/VCC/SCL/SDA'))
    for xx in (40,600):p.hole(xx,55);p.hole(xx,520)
    for i,name in enumerate(('GND','VCC','SCL','SDA')):p.pin(name,185+i*90,25,'T',name)
    p.s.rect(65,125,510,350,'#0b141b','#596e7c',7)
    p.s.text(110,210,'每人張數 17',36,'#7adaed',True)
    p.s.text(110,290,'玩家人數 3',36,'#7adaed',True)
    p.s.text(110,370,'餘牌張數 3',36,'#7adaed',True)

    for i,(name,title) in enumerate([('SW2','SET'),('SW3','-'),('SW4','+'),('SW5','RUN')]):
        p=add(Part(name,2780+i*330,1780,160,140,title+' 兩腳常開按鍵','#515d63','兩腳版；未按不通、按下導通'))
        p.s.rect(20,12,120,108,'#c5ccd0','#8496a2',12)
        p.s.add('circle',x=80,y=66,r=34,fill='#252c33',stroke='#5f717d')
        p.pin('1',15,75,'L',None);p.pin('2',145,75,'R',None)

    for name,x,y in [('Q1',120,3040),('Q2',2610,2940)]:
        p=add(Part(name,x,y,310,200,('Q1  旋轉參考' if name=='Q1' else 'Q2  出牌口')+' ITR9608-F','#283139','引腳側朝上（底視圖）；LED側在左'))
        p.s.rect(120,0,70,200,'#f8fafb','none',0)
        p.s.text(60,112,'LED',22,'white',True,'middle');p.s.text(245,112,'NPN',22,'white',True,'middle')
        for label,xx,yy,side in [('2=K',40,35,'T'),('1=A',40,165,'B'),('3=C',270,35,'T'),('4=E',270,165,'B')]:
            p.pin(label,xx,yy,side,label)

    for name,x,y,val in [('R1',650,3090,'150Ω'),('R2',2430,2680,'150Ω'),('R3',750,2820,'10kΩ'),
                          ('R4',2370,2450,'47kΩ'),('R5',2420,880,'10kΩ'),('R6',2420,1060,'10kΩ'),('R7',2420,1240,'10kΩ')]:
        p=add(Part(name,x,y,230,60,name+' '+val,'#eee9d9','電阻無方向'))
        p.s.rect(52,5,126,50,'#d8c99e','#b6a77f',18)
        bands={'150Ω':['#764e28','#267249','#764e28','#bca55d'],
               '10kΩ':['#764e28','#222222','#d27628','#bca55d'],
               '47kΩ':['#d5b632','#78439b','#d27628','#bca55d']}[val]
        for off,col in zip((75,100,125,155),bands):p.s.rect(off,9,9,42,col,col,0)
        p.pin('1',10,30,'L',None);p.pin('2',220,30,'R',None)

    for name,x,y,val in [('C1',650,1350,'470-1000µF/10V'),('C2',4100,2080,'470-1000µF/10V')]:
        p=add(Part(name,x,y,160,220,name+' '+val,'#e7edf1','電解電容：+接5V，-接GND'))
        p.s.rect(15,15,130,150,'#263b4b','#607c91',25)
        p.s.rect(108,24,25,132,'#b9cbd9','#b9cbd9',4)
        p.s.text(122,106,'-',33,INK,True,'middle')
        p.s.text(73,80,'10V',23,'white',True,'middle')
        p.pin('+',40,200,'B','+',False);p.pin('-',120,200,'B','-',False)
    for name,x,y in [('C3',3600,930),('C4',4030,1600)]:
        p=add(Part(name,x,y,150,130,name+' 100nF','#f1ece3','陶瓷104，無正負極'))
        p.s.add('circle',x=75,y=48,r=40,fill='#c4a279',stroke='#a27c4a')
        p.s.text(75,56,'104',21,INK,True,'middle')
        p.pin('1',35,110,'B',None);p.pin('2',115,110,'B',None)
    return parts


class Diagram:
    def __init__(self):
        self.parts=build_parts();self.pins={};self.obstacles=[];self.wires=[]
        self.occupied={};self.occ_dir={};self.branch_points=[]
        for p in self.parts:
            for name,pin in p.pins.items():
                key=p.key+'.'+name;assert key not in self.pins;self.pins[key]=pin
            self.obstacles.append((p.x-25,p.y-(105 if p.key=='ESP' else 65),p.x+p.w+25,p.y+p.h+65,p.key))
        # Ten complete conductors across an enlarged capsule cutaway; NC tails are shown separately.
        for i in range(12):
            yy=1050+i*95
            self.pins[f'SR{i+1:02}.F']=Pin(1960,yy,'L','SL1')
            self.pins[f'SR{i+1:02}.R']=Pin(2270,yy,'R','SL1')
        self.obstacles.append((1940,975,2290,2160,'SL1'))
        self.obstacles.append((2400,330,4320,592,'notes'))
        self.obstacles.append((1990,650,2250,930,'slip_icon'))
        self.obstacles.append((625,620,980,840,'usb_charger'))
        self.blocked=set()
        for x1,y1,x2,y2,_ in self.obstacles:
            for xx in range(math.floor(x1/PITCH),math.ceil(x2/PITCH)+1):
                for yy in range(math.floor(y1/PITCH),math.ceil(y2/PITCH)+1):self.blocked.add((xx,yy))

    def escape(self,pin):
        if pin.owner=='SL1':return (pin.x-70 if pin.side=='L' else pin.x+70,pin.y)
        part=next(p for p in self.parts if p.key==pin.owner)
        if pin.side=='L':return ((math.floor((part.x-25)/PITCH)-1)*PITCH,pin.y)
        if pin.side=='R':return ((math.ceil((part.x+part.w+25)/PITCH)+1)*PITCH,pin.y)
        if pin.side=='T':return (pin.x,(math.floor((part.y-65)/PITCH)-1)*PITCH)
        return (pin.x,(math.ceil((part.y+part.h+65)/PITCH)+1)*PITCH)

    def route(self,a,b,net,color,group):
        pa,pb=self.pins[a],self.pins[b]
        ea,eb=self.escape(pa),self.escape(pb)
        start=tuple(round(v/PITCH) for v in ea);goal=tuple(round(v/PITCH) for v in eb)
        try:points=self.astar(start,goal,net)
        except RuntimeError as e:
            owners=[(pos,owner) for pos in (start,goal) for x1,y1,x2,y2,owner in self.obstacles if x1<=pos[0]*PITCH<=x2 and y1<=pos[1]*PITCH<=y2]
            raise RuntimeError(f'{a} -> {b}; {e}; blocked endpoints={owners}') from e
        coords=[(pa.x,pa.y),ea]+[(x*PITCH,y*PITCH) for x,y in points]+[eb,(pb.x,pb.y)]
        # Only remove points exactly on the same straight segment.
        compact=[]
        for pt in coords:
            if compact and pt==compact[-1]:continue
            while len(compact)>=2 and (compact[-1][0]-compact[-2][0])*(pt[1]-compact[-1][1])==(compact[-1][1]-compact[-2][1])*(pt[0]-compact[-1][0]):compact.pop()
            compact.append(pt)
        self.wires.append({'a':a,'b':b,'net':net,'color':color,'group':group,'points':compact,'_grid':points})
        for j,(x,y) in enumerate(points):
            self.occupied.setdefault((x,y),set()).add(net)
            for k in (j-1,j+1):
                if 0<=k<len(points):
                    nx,ny=points[k];di=1 if nx!=x else 2
                    self.occ_dir.setdefault((x,y),set()).add((net,di))

    def astar(self,start,goal,net):
        serial=itertools.count();queue=[];came={};best={(start[0],start[1],0):0}
        heapq.heappush(queue,(0,next(serial),(start[0],start[1],0)))
        maxx,maxy=W//PITCH,H//PITCH
        finish=None;closed=set()
        while queue:
            _,_,state=heapq.heappop(queue);x,y,direction=state
            if state in closed:continue
            closed.add(state)
            g=best[state]
            if (x,y)==goal:finish=state;break
            for dx,dy,nd in [(1,0,1),(-1,0,1),(0,1,2),(0,-1,2)]:
                nx,ny=x+dx,y+dy;pos=(nx,ny)
                if not(1<=nx<=maxx-1 and 16<=ny<=maxy-3):continue
                if pos in self.blocked and pos not in (start,goal):continue
                occ=self.occupied.get(pos,set())
                cost=0.36 if net in occ else 1.0
                if direction and direction!=nd:cost+=2.4
                if occ-{net}:
                    if any(other!=net and od==nd for other,od in self.occ_dir.get(pos,set())):cost+=150
                    else:cost+=10
                ns=(nx,ny,nd);newg=g+cost
                if newg>=best.get(ns,1e30):continue
                best[ns]=newg;came[ns]=state
                h=(abs(nx-goal[0])+abs(ny-goal[1]))*0.35
                heapq.heappush(queue,(newg+h,next(serial),ns))
        if finish is None:raise RuntimeError(f'No route: {start}->{goal}')
        out=[]
        while True:
            out.append(finish[:2])
            if finish[:2]==start:break
            finish=came[finish]
        return out[::-1]


def selected_nets():
    return json.loads((ROOT/'source/wiring/logical_nets.json').read_text(encoding='utf8'))


def style(net):
    if 'GND' in net:return BLACK,'power'
    if net.startswith('+5V') or net in ('PACK+','PACK_SW+','BAT_RAW+'):return RED,'power'
    if net=='BAT_RAW-':return BLACK,'power'
    if net.startswith('+3V3'):return GREEN,'power'
    if 'SDA' in net:return COLORS[3],'ui'
    if 'SCL' in net:return COLORS[4],'ui'
    if 'AIN1' in net:return COLORS[5],'motor'
    if 'AIN2' in net:return COLORS[6],'motor'
    if 'BIN1' in net:return COLORS[7],'motor'
    if 'EXIT' in net:return COLORS[8],'sensor'
    if 'HOME' in net:return COLORS[9],'sensor'
    if net.startswith('ULN_IN'):return ['#d2760d','#4f88c1','#9364bd','#41896d'][int(net[-1])-1],'stepper'
    if 'M1_HARNESS' in net:return [RED,'#328cc4','#d66a9f','#d2b333','#cf7a2b'][int(net[-1])-1],'stepper'
    if net.startswith('KEY'):return '#436bba','ui'
    if 'LED' in net:return '#c34b34','sensor'
    if net.startswith(('M2','M3')):return '#7654a9','motor'
    return '#4b7897','sensor'


def route_all(d,nets):
    collisions=[]
    for key in {pin for pins in nets.values() for pin in pins}:
        p=d.pins[key];pt=tuple(round(v/PITCH) for v in d.escape(p))
        if pt in d.blocked:
            owners=[owner for x1,y1,x2,y2,owner in d.obstacles if x1<=pt[0]*PITCH<=x2 and y1<=pt[1]*PITCH<=y2]
            collisions.append((key,pt,owners))
    if collisions:raise RuntimeError(f'Layout requires space for lead exits: {collisions}')
    # Local motor leads and the longer cross-system nets remain separately selectable.
    for name,pins in nets.items():
        color,group=style(name)
        assert len(pins)>=2
        for pin in pins:assert pin in d.pins,pin
        root=pins[0]
        for dest in pins[1:]:
            d.route(root,dest,name,color,group)
    # The slipring itself is an electrical connection, not an external jumper.
    for j in range(10):
        a,b=f'SR{j+1:02}.F',f'SR{j+1:02}.R'
        color=COLORS[j];group=['power','power','power','ui','ui','motor','motor','motor','sensor','sensor'][j]
        pa,pb=d.pins[a],d.pins[b]
        d.wires.append({'a':a,'b':b,'net':'SLIP_'+str(j+1),'color':color,'group':group,
                        'points':[(pa.x,pa.y),(pb.x,pb.y)],'internal':True})
    for wire in d.wires:
        a,b=d.pins[wire['a']],d.pins[wire['b']]
        assert wire['points'][0]==(a.x,a.y) and wire['points'][-1]==(b.x,b.y)
    return d


def background():
    s=Scene(W,H)
    s.rect(0,0,W,H,'#f8fafc','none',0)
    s.text(55,76,'撲克牌發牌機 - 實物風格逐腳接線圖',49,INK,True)
    s.text(58,125,'V1.0.0  |  沿著每一條彩色線即可找到兩端焊孔  |  ESP32-C3 SuperMini / V1.0.0',28,GRAY)
    s.rect(45,198,1810,H-292,'#eef4f8','#cedbe5',24)
    s.rect(2385,198,1970,H-292,'#f0f7f2','#c8dfd0',24)
    s.text(78,249,'固定底盒：電池、充電／保護／升壓、ESP、步進與參考感測器',29,INK,True)
    s.text(2410,249,'旋轉上半部：直流馬達、出牌感測、螢幕與按鍵',29,INK,True)
    s.text(78,168,'PCB與零件放大比例不同；固定座、導線長度不按本圖量取。',23,GRAY)
    s.text(2410,290,'完整走線跨越滑環；圓點是焊接分支，沒有圓點的交叉不相接。',23,GRAY)
    s.text(55,H-41,'2026-11-08 | 指定參考板型，非實機照片。接電腦USB前先拔JP-ESP5V。充電時SW1關閉。',24,INK)
    s.text(W-55,H-41,'逐條導線 / 端點可追蹤',24,GRAY,anchor='end')
    s.text(650,665,'既有 5V / 2A 充電器',25,INK,True)
    s.rect(650,690,230,135,'#d5dce3','#718390',17)
    s.text(760,747,'5V / 2A',29,INK,True,'middle')
    s.rect(852,730,28,40,'#29353f','#556776',4)
    s.line([(880,750),(960,750),(960,985),(1065,985)],BLACK,12)
    s.text(990,955,'USB Type-C線',20,GRAY)
    return s


def capsule_scene():
    s=Scene(W,H)
    s.text(2115,580,'SL1  12路滑環',31,INK,True,'middle')
    s.text(2115,622,'兩端導線逐條攤開',22,GRAY,anchor='middle')
    # A small front/side pictorial icon above the enlarged cutaway.
    s.rect(2040,700,150,150,'#303941','#62727d',35)
    s.rect(2005,815,220,35,'#222e38','#596b78',15)
    for j in range(6):
        s.line([(2070+j*17,700),(2070+j*17,663)],COLORS[j],5,halo=False)
        s.line([(2070+j*17,850),(2070+j*17,895)],COLORS[j+4],5,halo=False)
    s.rect(1935,980,360,1195,'#35424b','#5e7382',65)
    s.rect(1960,1000,310,1150,'#edf2f6','#ccd7df',40)
    for j in range(12):
        yy=1050+j*95
        s.text(2115,yy-18,f'{j+1:02}',20,GRAY,True,'middle')
        if j>=10:
            s.line([(1910,yy),(2320,yy)],'#99a4ac',4,True)
            s.rect(1885,yy-8,25,16,'#2c3740','#2c3740',3)
            s.rect(2320,yy-8,25,16,'#2c3740','#2c3740',3)
    for yy,text in [(2242,'上方圖示為實物外形'),(2281,'中間放大內部導通'),(2320,'不是20腳排針插座'),(2380,'11 / 12兩端各自絕緣')]:
        s.text(2115,yy,text,23,GRAY,anchor='middle')
    return s


def complete_scene(d,active=None,include_wires=True):
    s=background();s.group(capsule_scene())
    for p in d.parts:s.group(p.s,p.x,p.y)
    # Signal wire jackets have a pale gap where another wire passes underneath.
    ordered=sorted(d.wires,key=lambda w:w['group']!='power')
    for wire in ordered if include_wires else []:
        if active and wire['group']!=active:
            s.line(wire['points'],'#dce2e7',3,halo=False)
        else:s.line(wire['points'],wire['color'],5 if wire['group']=='power' else 4,halo=True)
    # Contact dots make the actual source/target holes unambiguous after routing.
    contacts={}
    for wire in d.wires:
        if active and wire['group']!=active:continue
        for endpoint in (wire['a'],wire['b']):contacts[endpoint]=wire['color']
    for key,color in contacts.items():
        pin=d.pins[key];s.dot(pin.x,pin.y,color,5)
    for x,y,net,color,group in d.branch_points:
        if not active or active==group:s.dot(x,y,color,6)
    s.note(2435,395,1825,[
        'PCB旁標明「元件面」或「焊接面」；先把實物轉成相同方向，再照焊孔接。',
        'EEP只接本HW-627的VCC=5V，不接ESP GPIO或3V3。其餘控制訊號仍為3.3V。',
        '本PCF板已有I2C上拉，不另加R8/R9；地址帽在另一面，A0/A1/A2都選GND。',
    ],fill='#fff8e9',size=22,step=35)
    return s


def union_checks(d,nets):
    parent={pin:pin for pin in d.pins}
    def find(pin):
        if parent[pin]!=pin:parent[pin]=find(parent[pin])
        return parent[pin]
    for wire in d.wires:parent[find(wire['a'])]=find(wire['b'])
    def same(*pins):return len({find(p) for p in pins})==1
    for gpio,pin in [(0,'ULN2003.IN1'),(1,'ULN2003.IN2'),(3,'ULN2003.IN3'),(4,'ULN2003.IN4'),
                     (5,'DRV8833.IN1'),(6,'DRV8833.IN2'),(7,'DRV8833.IN3'),(10,'Q2.3=C')]:
        assert same('ESP.GPIO'+str(gpio),pin)
    assert same('ESP.GPIO21','PCF.SDA','OLED.SDA')
    assert same('ESP.GPIO20','PCF.SCL','OLED.SCL')
    assert same('PCF.P4','Q1.3=C')
    assert same('ESP.3V3','PCF.VCC','OLED.VCC')
    assert same('1S保護板.P-','ESP.GND','DRV8833.GND','DRV8833.IN4','Q1.4=E','Q2.4=E')
    assert not same('1S保護板.B-','ESP.GND')
    assert same('TPS61088.OUT+','DRV8833.VCC','DRV8833.EEP')
    assert not same('TPS61088.OUT+','ESP.5V') # disconnected JP branch is an actual gap
    for pin in ('DRV8833.OUT1','DRV8833.OUT2','DRV8833.OUT3','DRV8833.OUT4'):
        assert not same(pin,'DRV8833.GND') and not same(pin,'DRV8833.VCC')
    for pin in ['ESP.GPIO2','ESP.GPIO8','ESP.GPIO9','DRV8833.ULT','PCF.P5','PCF.P6','PCF.P7','PCF.INT']:
        assert all(w['a']!=pin and w['b']!=pin for w in d.wires)
    return {pin:find(pin) for pin in parent}


def svg_diagram(d,active=None):
    # The same deterministic vector geometry used in the PDF, with selectable wire layers.
    base=complete_scene(d,active,include_wires=False)
    # Build SVG for all components before adding interactive wire groups.
    svg=v.to_svg(base)
    # Scene's complete wires are replaced by an interaction overlay with a wider invisible hit path.
    overlay=[]
    for i,wire in enumerate(d.wires):
        pts=' '.join(f'{x},{y}' for x,y in wire['points'])
        meta=escape(json.dumps({k:wire[k] for k in ('a','b','net','group')},ensure_ascii=False),quote=True)
        width=5 if wire['group']=='power' else 4
        overlay.append(f'<g class="trace" data-wire="{i}" data-net="{escape(wire["selection"])}" data-group="{wire["group"]}" data-info="{meta}"><title>{escape(wire["a"]+" → "+wire["b"])}</title><polyline points="{pts}" fill="none" stroke="white" stroke-width="{width+3}" pointer-events="none"/><polyline class="jacket" points="{pts}" fill="none" stroke="{wire["color"]}" stroke-width="{width}" pointer-events="none"/><polyline points="{pts}" fill="none" stroke="transparent" stroke-width="20" pointer-events="stroke"/><polyline class="highlight" points="{pts}" fill="none" stroke="{wire["color"]}" stroke-width="9" opacity="0" pointer-events="none"/></g>')
    return svg.replace('</svg>', '\n'+''.join(overlay)+'</svg>')


def atlas(d):
    pages=[]
    def body_view(part):
        result=Scene(part.w,part.h)
        result.ops=[(kind,args) for kind,args in part.s.ops
                    if kind!='text' or 0<=args['y']<=part.h]
        return result
    groups=[('板型與觀看方向 1 / 4',['ESP','TP4056','TPS61088','1S保護板']),
            ('板型與觀看方向 2 / 4',['DRV8833','N20','OLED','ULN2003']),
            ('光電、按鍵與供電操作 4 / 4',['Q1','Q2','SW2','JP-ESP5V'])]
    for title,keys in groups:
        s=Scene(1600,1131);s.rect(0,0,1600,1131,'white','none',0)
        s.text(35,58,title,35,INK,True)
        s.text(37,97,'本頁用來比對實物板型；完整連線請開啟主圖或互動HTML。',22,GRAY)
        for i,key in enumerate(keys):
            p=next(p for p in d.parts if p.key==key)
            x=45+(i%2)*785;y=185+(i//2)*435
            scale=min(1.35,700/p.w,275/p.h)
            xx=x+(700-p.w*scale)/2
            s.text(x,y-32,p.title,24,INK,True,maxw=710)
            s.group(body_view(p),xx,y,scale)
            lines=[];line=''
            for ch in p.view:
                if v.pdfmetrics.stringWidth(line+ch,'CJK',20)>710:lines.append(line);line=''
                line+=ch
            if line:lines.append(line)
            for j,line in enumerate(lines[:2]):s.text(x,y+p.h*scale+33+j*28,line,20,GRAY)
        s.text(40,1053,'指定型號的焊孔順序必須與圖相同；板色可能不同。未做實物通電／送牌測試。',21,GRAY)
        s.text(40,1097,'接線圖V1.0.0 / 韌體V1.0.0 | 2026-11-08',18,GRAY)
        pages.append(s)
    s=Scene(1600,1131);s.rect(0,0,1600,1131,'white','none',0)
    s.text(35,58,'PCF8574T：背面排針與正面地址帽 3 / 4',34,INK,True)
    s.text(37,105,'主圖與下方大圖都是焊接面；P0在左，INT在右。不要直接照正面的左右位置接。',23,GRAY)
    p=next(p for p in d.parts if p.key=='PCF');scale=1.15;xx=95;yy=220
    s.text(xx,180,'背面 / 焊接面',27,INK,True)
    s.group(body_view(p),xx,yy,scale)
    s.text(105,635,'翻到正面，三個地址帽都跨「中間A」與「- / GND」兩針。',25,INK,True)
    for j,label in enumerate(('A2','A1','A0')):
        y=740+j*90
        s.text(105,y+8,label,27,INK,True)
        for x in (240,340,440):s.add('circle',x=x,y=y,r=13,fill='#bda451',stroke='#ead69b')
        s.rect(320,y-22,140,44,'#e9cc51','#a68b24',9)
        for x in (340,440):s.add('circle',x=x,y=y,r=8,fill='#7f6d2c',stroke='#9c852e')
    for x,label in [(240,'+ / VCC'),(340,'A'),(440,'- / GND')]:s.text(x,695,label,22,GRAY,anchor='middle')
    s.note(660,706,845,[
        'PCF8574T，7bit地址0x20；不是PCF8574A。',
        'P0=SET；P1=-；P2=+；P3=RUN；P4=參考。',
        'P5/P6/P7與INT不外接。',
        '模組已帶I2C上拉，主圖不再外加R8/R9。',
        'PCB尺寸與原CAD假定不同，固定座須重新試配。',
    ],title='本版接法',size=21,step=35)
    s.text(40,1088,'接線圖V1.0.0 / 韌體V1.0.0 | 2026-11-08',18,GRAY)
    pages.insert(2,s)
    return pages


def branch_dots(d):
    adjacency={};info={}
    for wire in d.wires:
        info[wire['net']]=(wire['color'],wire['group'])
        grid=wire.get('_grid',[])
        for a,b in zip(grid,grid[1:]):
            adjacency.setdefault((wire['net'],tuple(a)),set()).add(tuple(b))
            adjacency.setdefault((wire['net'],tuple(b)),set()).add(tuple(a))
    for (net,pt),neighbors in adjacency.items():
        if len(neighbors)>=3:
            color,group=info[net]
            d.branch_points.append((pt[0]*PITCH,pt[1]*PITCH,net,color,group))


def html_viewer(d,svg):
    metadata=[{k:value for k,value in wire.items() if k not in ('points','_grid')} for wire in d.wires]
    template=r'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>發牌機 V1.0.0 - 實物接線圖</title>
<style>
*{box-sizing:border-box}body{margin:0;font:15px 'Microsoft JhengHei',system-ui,sans-serif;background:#e9eff4;color:#152e43}
header{padding:13px 20px;background:#183a53;color:white;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
h1{font-size:20px;margin:0}header p{margin:0;color:#cfdee9;font-size:13px}button,select,input{font:inherit;border:1px solid #b9c8d3;border-radius:6px;padding:7px 11px;background:white;color:#173a53}
button{cursor:pointer}button:hover{background:#e7f0f6}.toolbar{display:flex;gap:8px;align-items:center;padding:9px 15px;background:white;flex-wrap:wrap}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;height:calc(100vh - 122px)}
#board{overflow:hidden;touch-action:none;background:#f7fafc;cursor:grab}#board.drag{cursor:grabbing}#board svg{width:100%;height:100%;display:block;user-select:none}
aside{background:white;border-left:1px solid #c7d5df;overflow:auto;padding:16px}aside h2{margin:0 0 10px;font-size:17px}
.help{font-size:13px;color:#506a7d;line-height:1.7}.notice{padding:11px;border-radius:8px;background:#fff3de;margin:12px 0;font-size:13px;line-height:1.7}
#info{min-height:95px;padding:12px;background:#edf4f8;border-radius:8px;line-height:1.8;overflow-wrap:anywhere}
#list{margin:12px 0;padding:0;list-style:none}#list button{display:block;width:100%;text-align:left;font-size:12px;line-height:1.6;margin:5px 0;overflow-wrap:anywhere}
.trace{cursor:pointer}.trace.dim{opacity:.09}.trace.selected .highlight{opacity:1}.trace:hover .highlight{opacity:.9}
.source{font-size:12px;color:#586f7f;line-height:1.6}@media(max-width:850px){.layout{grid-template-columns:1fr;grid-template-rows:70vh auto;height:auto}aside{border-top:1px solid #c7d5df}.toolbar{padding:8px}h1{font-size:17px}}
</style>
<header><h1>發牌機 - 實物逐腳接線圖 V1.0.0</h1><p>所有線都有完整路徑；按線可顯示兩端接腳。可離線使用。</p></header>
<div class="toolbar"><select id="group"><option value="all">顯示全部導線</option><option value="power">1 電源／充電／接地</option><option value="stepper">2 步進與原5芯線</option><option value="motor">3 DRV與兩顆直流馬達</option><option value="ui">4 螢幕與四顆按鍵</option><option value="sensor">5 兩顆光電感測器</option></select>
<button id="plus">放大 +</button><button id="minus">縮小 -</button><button id="fit">全圖</button><button id="clear">取消選線</button><span class="help">滾輪縮放；拖曳空白處移動。</span></div>
<div class="layout"><main id="board">__SVG__</main><aside><h2>逐條追線</h2><div id="info">點一條線，這裡會顯示起點、終點與同網路的所有分支。</div>
<div class="notice">先把PCB轉成圖上標示的觀看方向。PCF8574與HW-627畫的是焊接面。滑環線色需先量通斷自行配對。</div>
<p class="help">同一個接腳可分出數條線；圓點表示實際焊接分支。沒有圓點的交叉，彼此不相接。</p>
<input id="search" placeholder="搜尋 GPIO21、PCF.P4、TP4056…" style="width:100%"><ul id="list"></ul>
<p class="source">EEP這一腳使用本HW-627的VCC=5V喚醒，無需接3V3。PCF模組自帶I2C上拉，不重複加R8/R9。<br>圖面未作實機通電測試，選購板型與尺寸差異請看附檔。</p></aside></div>
<script>
const wires=__DATA__,board=document.querySelector('#board'),svg=board.querySelector('svg'),traces=[...svg.querySelectorAll('.trace')];
let currentGroup='all',selected=null,box=[0,0,4400,3400],drag=null;
function view(){svg.setAttribute('viewBox',box.join(' '))}function changeZoom(f,cx,cy){let p=svg.createSVGPoint();p.x=cx;p.y=cy;p=p.matrixTransform(svg.getScreenCTM().inverse());let nw=Math.min(8800,Math.max(350,box[2]*f)),ratio=nw/box[2];box=[p.x+(box[0]-p.x)*ratio,p.y+(box[1]-p.y)*ratio,nw,box[3]*ratio];view()}
function update(){traces.forEach((t,i)=>{const w=wires[i],sel=selected!==null&&w.selection===selected;let dim=(currentGroup!=='all'&&w.group!==currentGroup)||(selected!==null&&!sel);t.classList.toggle('dim',dim);t.classList.toggle('selected',sel)});renderList()}
function choose(i){selected=wires[i].selection;const group=wires.filter(w=>w.selection===selected);document.querySelector('#info').textContent=group.map(w=>w.a+' → '+w.b+(w.internal?'（滑環內部導通）':'')).join('\n');document.querySelector('#info').style.whiteSpace='pre-line';update()}
function renderList(){let q=document.querySelector('#search').value.toLowerCase(),ul=document.querySelector('#list');ul.replaceChildren();wires.forEach((w,i)=>{if(currentGroup!=='all'&&w.group!==currentGroup)return;if(q&&!JSON.stringify(w).toLowerCase().includes(q))return;let li=document.createElement('li'),b=document.createElement('button');b.textContent=w.a+' → '+w.b;b.style.borderLeft='5px solid '+w.color;b.onclick=()=>choose(i);li.append(b);ul.append(li)})}
traces.forEach((t,i)=>t.addEventListener('click',e=>{e.stopPropagation();choose(i)}));
document.querySelector('#group').onchange=e=>{currentGroup=e.target.value;selected=null;update()};
document.querySelector('#search').oninput=renderList;
document.querySelector('#clear').onclick=()=>{selected=null;document.querySelector('#info').textContent='點選導線或右側清單查看兩端。';update()};
document.querySelector('#fit').onclick=()=>{box=[0,0,4400,3400];view()};
function centerZoom(f){let r=board.getBoundingClientRect();changeZoom(f,r.x+r.width/2,r.y+r.height/2)}
document.querySelector('#plus').onclick=()=>centerZoom(.8);document.querySelector('#minus').onclick=()=>centerZoom(1.25);
board.addEventListener('wheel',e=>{e.preventDefault();changeZoom(e.deltaY>0?1.15:1/1.15,e.clientX,e.clientY)},{passive:false});
board.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('.trace'))return;drag={x:e.clientX,y:e.clientY,box:[...box]};board.classList.add('drag');board.setPointerCapture(e.pointerId)});
board.addEventListener('pointermove',e=>{if(!drag)return;let r=board.getBoundingClientRect(),scale=Math.min(r.width/drag.box[2],r.height/drag.box[3]);box=[drag.box[0]-(e.clientX-drag.x)/scale,drag.box[1]-(e.clientY-drag.y)/scale,drag.box[2],drag.box[3]];view()});
board.addEventListener('pointerup',()=>{drag=null;board.classList.remove('drag')});view();renderList();
</script></html>'''
    return template.replace('__SVG__',svg[svg.index('<svg'):]).replace('__DATA__',json.dumps(metadata,ensure_ascii=False).replace('</',r'<\/'))


def main():
    v.validate_fw()
    d=Diagram();nets=selected_nets()
    key=hashlib.sha256(json.dumps({'pins':{k:[p.x,p.y,p.side,p.owner] for k,p in d.pins.items()},'bounds':d.obstacles,'nets':nets},sort_keys=True,ensure_ascii=True).encode()).hexdigest()
    cache=ROOT/'source/pictorial/routes-cache.json'
    prior=json.loads(cache.read_text(encoding='utf8')) if cache.exists() else {}
    if prior.get('key')==key:
        d.wires=prior['wires']
        for wire in d.wires:wire['points']=[tuple(p) for p in wire['points']]
    else:
        route_all(d,nets)
        cache.write_text(json.dumps({'key':key,'wires':d.wires}),encoding='utf8')
    branch_dots(d);components=union_checks(d,nets)
    for wire in d.wires:wire['selection']=components[wire['a']]
    print(f'Routed {len(d.wires)} complete paths; validating exact source and target pads.',flush=True)
    main_scene=complete_scene(d)
    from reportlab.lib.pagesizes import A1,A4,landscape
    pdf=OUT/'發牌機_實物逐腳接線圖_A1.pdf'
    atlas_pdf=OUT/'指定板型與觀看方向_A4.pdf'
    v.write_pdf(pdf,[main_scene],landscape(A1))
    v.write_pdf(atlas_pdf,atlas(d),landscape(A4))
    svg=svg_diagram(d)
    (OUT/'發牌機_實物逐腳接線圖.svg').write_text(svg,encoding='utf8')
    (OUT/'開啟我_互動實物接線圖.html').write_text(html_viewer(d,svg),encoding='utf8')
    metadata=[{k:value for k,value in wire.items() if k!='_grid'} for wire in d.wires]
    (OUT/'逐線端點與路徑.json').write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf8')
    with (OUT/'逐線接腳清單.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['編號','起點焊孔','終點焊孔','網路','分組','說明'])
        for i,w in enumerate(d.wires):writer.writerow([i+1,w['a'],w['b'],w['net'],w['group'],'滑環內部已導通，非外加線' if w.get('internal') else '依圖上觀看方向接實體焊孔'])
    pinmap={p.key:{'title':p.title,'view':p.view,'bounds':[p.x,p.y,p.w,p.h],
                   'pins':{name:[pin.x,pin.y,pin.side] for name,pin in p.pins.items()}} for p in d.parts}
    (OUT/'板型與焊孔位置.json').write_text(json.dumps(pinmap,ensure_ascii=False,indent=2),encoding='utf8')
    readme='''發牌機實物接線圖 V1.0.0 - 對應V1.0.0

先開「開啟我_互動實物接線圖.html」。不需網路、不需安裝軟體。
每條線都從一個實體焊孔畫到另一個焊孔；沒有以兩個同名線號代替連線。
按導線或右側清單，可顯示兩端與同網路分支；下拉選單可單獨顯示電源、步進、直流馬達、UI或光電。
滾輪縮放、空白處拖曳；全圖按鈕復位。PDF與PNG同樣是完整走線。
滑環以放大剖面顯示其內部導通，並非20腳連接器；不要再加線直接跨越固定與旋轉兩邊。
滑環每對線先斷電量通斷，按圖中01-12配對，再套熱縮標號；原廠沒有通用線色。

觀看方向（很重要）：
ESP32-C3 SuperMini：元件面朝上、USB向上；左右8孔依廠商接腳圖。
TP4056 HW-387：元件面，USB向左，右上BAT+、右下BAT-，左IN+/IN-不外接。
TPS61088：黑色四角焊孔、5/9/12/ADJ焊盤款，VIN左上、GND左下、VOUT右上、GND右下。
1S保護板：指定35×7.4mm長條DW01/三8205A款，焊接面朝上。B-最左、B+最右；P-中右上、P+中右下。
ULN2003：X113647/ZC-A0591七輸入款，元件面。底排IN1-IN7由左向右，用前四孔；右側電源下兩孔為+和-，上兩孔原跳帽保留。
DRV8833：HW-627十二腳黑板，焊接面，J2在上。左列IN4/IN3/GND/VCC/IN2/IN1；右列EEP/OUT1/OUT2/OUT3/OUT4/ULT。
PCF8574T：Waveshare式長條9孔IO款，畫的是焊接面！IO排由左到右P0/P1/P2/P3/P4/P5/P6/P7/INT；右側四孔由上到下VCC/GND/SDA/SCL。
OLED：選正面排針由左到右GND/VCC/SCL/SDA的SSD1306 128x64四孔板，排針在上。地址0x3C。
Q1/Q2：Everlight ITR9608-F，底視圖，發光端在左；左上2=K、左下1=A、右上3=C、右下4=E。
按鍵：指定兩腳6×6常開型；不按斷路、按下導通，兩腳沒有極性。四腳版不能照兩腳位置套接。

指定板型的接法與適配：
HW-627的EEP是nSLEEP，圖中一條線把它接同一塊板的VCC=5V，保持喚醒。
這是DRV8833允許的接法，與本板J2是否已接VM不衝突；不要把EEP再接3V3或ESP GPIO。
本指定PCF板內建SDA/SCL上拉，因此不額外安裝選配R8/R9。若所購版不同，先核對總等效上拉與3.3V邏輯；不是所有板都同阻值。
地址跳帽在PCF另一面，A0/A1/A2均跨中間A與標示「-」的GND側，7bit地址0x20。
PCF模組上的兩顆I2C上拉與OLED可能並聯，須核對實物；匯流排以100kHz、3.3V運作。
R1/R2=150Ω/1/4W，各供一顆IR LED；R3=10kΩ出口上拉；R4=47kΩ參考上拉；R5/R6/R7各10kΩ輸入下拉。
C1/C2=470-1000µF/10V電解；C3/C4=100nF陶瓷，分別接在兩顆直流馬達兩端。
PCF與OLED保留模組原有旁路電容。若實購模組沒有，另補100nF在VCC-GND附近。
所有GPIO、玩家角度及發牌邏輯沒有改變；不需重燒另一套接腳韌體。

供電：
TP4056的BAT+/BAT-都接保護板P端，不接原始B-；系統GND為P-。
SW1串在P+到升壓VIN；充電時SW1關閉。充電走TP4056 Type-C，電流先設0.5A。
升壓先量5.00V才接ESP與馬達；EEP上的5V不是可接ESP GPIO的邏輯輸出。
ESP 5V分支經JP-ESP5V：兩針排針加可拔短路帽，帽跨兩針時導通，取下時斷開5V。
接電腦USB前先拔JP跳帽，GND固定共地。普通電池工作時開發板USB不接電腦。

機構適配界限：
本次把「可核對孔序」的參考板型固定下來，沒有更改原CAD或聲稱實物已組裝。
原CAD只按參考尺寸建模；本指定PCF長條板與X113647驅動板，外形可能大於原29×20等假定包絡。
購買前核對所選板的實際長寬與目前固定座，這兩處支架須重新試配／調整，不能以接線圖作孔距或機構已通過的證明。
配線圖各零件採不同放大倍率，不按畫面距離裁導線。線材預留拆裝餘量並固定，避免捲入齒輪。

參考來源（用於腳位／板型核對，不是即時價格或保證庫存）：
SuperMini官方接腳圖：
https://www.nologo.tech/product/esp32/esp32c3/esp32c3supermini/esp32C3SuperMini.html
TP4056 HW-387 Type-C無保護板產品實照：
https://easyelecmodule.com/product/tp4056-type-c-interface-no-protection/
TPS61088四角黑板實照：
https://www.orwintech.com/TechnologyDetail/tps61088-boost-converter-step-up-board-power-supply-module
PCF8574T長條板正反面及原理圖：
https://www.openimpulse.com/blog/products-page/product-category/pcf8574-io-expansion-module/
https://www.openimpulse.com/blog/wp-content/uploads/wpsc/downloadables/PCF8574-IO-Expansion-Module-Schematic.pdf
HW-627焊接面腳序產品圖：
https://www.orwintech.com/TechnologyDetail/drv8833-dual-h-bridge-motor-driver-module-complete-guide
DRV8833電氣限制（nSLEEP、VM、3.3V控制）：
https://www.ti.com/lit/ds/symlink/drv8833.pdf
1S 5A長條保護板實物焊接面與B/P端：
https://done.land/components/power/powersupplies/battery/bms/1s/5a/
ULN2003 X113647實照：ELEGOO Mega2560 Starter Kit Tutorial，PDF第210頁。
https://images-na.ssl-images-amazon.com/images/I/D1oC-c3G5TS.pdf
ITR9608-F原廠腳位：
https://media.digikey.com/pdf/data%20sheets/everlight%20pdfs/itr9608-f.pdf

本圖為依上述板型資料繪製的實物風格插圖，沒有使用AI生成文字或隨機導線。
已核對每條連線兩端與V1.0.0 GPIO，並檢查10路滑環後的導通；尚未實物通電、送牌或電源雜訊驗證。
'''
    (OUT/'先讀_參考板型與接線說明.txt').write_text(readme,encoding='utf-8-sig')
    # Print and inspect the actual PDF rendering.
    subprocess.run([str(v.POPPLER),'-singlefile','-scale-to','6200','-png',str(pdf),str(OUT/'發牌機_實物逐腳接線圖')],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    subprocess.run([str(v.POPPLER),'-scale-to','1900','-png',str(atlas_pdf),str(TMP/'atlas')],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    from PIL import Image
    with Image.open(OUT/'發牌機_實物逐腳接線圖.png') as im:
        im.thumbnail((3200,2600));im.save(OUT/'實物接線圖_預覽.png')
    # All-image groups are supplied for a simple non-interactive fallback.
    for group,title in [('power','1_電源'),('stepper','2_步進'),('motor','3_直流馬達'),('ui','4_螢幕按鍵'),('sensor','5_感測器')]:
        path=TMP/(group+'.pdf');v.write_pdf(path,[complete_scene(d,group)],landscape(A1))
        subprocess.run([str(v.POPPLER),'-singlefile','-scale-to','4400','-png',str(path),str(OUT/title)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    verification={'version':'V1.0.0','date':'2026-11-08','firmware':'V1.0.0','wire_paths':len(d.wires),
                  'all_paths_terminate_on_defined_physical_pads':True,'slipring_internal_paths':10,
                  'firmware_continuity_checks':True,'raw_battery_negative_isolated':True,
                  'usb_branch_isolated_with_JP_open':True,'hardware_tested':False,'mechanical_refit_required':['PCF8574 long board holder','X113647 holder'],
                  'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='verification.json'}}
    (OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'out':str(OUT),'wire_paths':len(d.wires),'files':len(list(OUT.iterdir()))},ensure_ascii=True),flush=True)


if __name__=='__main__':main()


