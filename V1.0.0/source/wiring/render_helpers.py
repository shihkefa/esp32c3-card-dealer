"""Shared SVG/PDF rendering primitives and wiring checks for V1.0.0."""
from pathlib import Path
from copy import deepcopy
from html import escape
from math import hypot
import csv
import hashlib
import json
import re
import subprocess
import zipfile

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import toColor as HexColor
from reportlab.lib.pagesizes import A2, A4, landscape
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'wiring'
TMP = ROOT / '.build/wiring'
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
POPPLER = Path(r'C:\Users\shihk\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
pdfmetrics.registerFont(TTFont('CJK', r'C:\Windows\Fonts\msjh.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('CJKB', r'C:\Windows\Fonts\msjhbd.ttc', subfontIndex=0))

INK = '#172d43'
MUTED = '#4c6173'
GRID = '#c8d4df'
BG = '#f2f6f9'
V5 = '#c33338'
V3 = '#00796f'
GND = '#354657'
SIG = '#1c66b3'
HOME = '#aa5900'
MOTOR = '#724aa0'
BAT = '#ba2455'


class Scene:
    def __init__(self, w, h):
        self.w, self.h, self.ops = w, h, []

    def add(self, kind, **args):
        self.ops.append((kind, args))

    def rect(self, x, y, w, h, fill='white', stroke=GRID, radius=10, width=1.4):
        self.add('rect', x=x, y=y, w=w, h=h, fill=fill, stroke=stroke, radius=radius, width=width)

    def text(self, x, y, value, size=20, color=INK, bold=False, anchor='start', maxw=None):
        font = 'CJKB' if bold else 'CJK'
        if maxw:
            size = min(size, size * maxw / max(1, pdfmetrics.stringWidth(value, font, size)))
        assert size >= 13, (value, size)
        self.add('text', x=x, y=y, value=value, size=size, color=color, bold=bold, anchor=anchor)

    def line(self, points, color=SIG, width=2.8, dashed=False, halo=True):
        self.add('line', points=points, color=color, width=width, dashed=dashed, halo=halo)

    def dot(self, x, y, color=SIG, r=4):
        self.add('circle', x=x, y=y, r=r, fill=color, stroke=color)

    def port(self, x, y, color=SIG):
        self.add('circle', x=x, y=y, r=4, fill='white', stroke=color)

    def group(self, other, x=0, y=0, scale=1, clip=None):
        self.add('group', scene=other, x=x, y=y, scale=scale, clip=clip)

    def note(self, x, y, w, lines, title=None, fill='#f5f8fa', size=19, step=29):
        h = len(lines) * step + (48 if title else 25)
        self.rect(x, y, w, h, fill=fill)
        yy = y + 29
        if title:
            self.text(x + 18, yy, title, 23, bold=True, maxw=w-36)
            yy += 34
        for value in lines:
            self.text(x + 18, yy, value, size, maxw=w-36)
            yy += step
        return h

    def block(self, x, y, w, h, title, subtitle=None, accent=INK):
        self.rect(x, y, w, h, fill='white', stroke=accent, width=1.8)
        self.rect(x + 1, y + 1, w - 2, 48, fill='#edf3f8', stroke='none', radius=9)
        self.text(x + 16, y + 33, title, 24, accent, True, maxw=w-32)
        if subtitle:
            self.text(x + 16, y + 75, subtitle, 18, MUTED, maxw=w-32)

    def flag(self, x, y, value, color=SIG, side='right', length=72, size=19):
        end = x + length if side == 'right' else x - length
        self.line([(x, y), (end, y)], color)
        self.port(x, y, color)
        self.text(end + (7 if side == 'right' else -7), y + 6, value, size, color,
                  anchor='start' if side == 'right' else 'end')

    def resistor(self, x1, y, x2, label, color=SIG):
        assert x2 - x1 >= 65
        mid = (x1 + x2) / 2
        self.line([(x1, y), (mid - 25, y)], color)
        self.rect(mid - 25, y - 9, 50, 18, fill='white', stroke=color, radius=0, width=2)
        self.line([(mid + 25, y), (x2, y)], color)
        self.text(mid, y - 17, label, 18, color, anchor='middle')

    def cap(self, x, y, label, top=V5, bottom=GND, polarized=True):
        self.line([(x, y), (x, y + 26)], top)
        self.line([(x-17, y+26), (x+17, y+26)], top, halo=False)
        self.line([(x-17, y+37), (x+17, y+37)], bottom, halo=False)
        self.line([(x, y + 37), (x, y + 65)], bottom)
        self.text(x + 25, y + 33, label, 17, MUTED)
        if polarized:
            self.text(x - 29, y + 18, '+', 19, top)




def to_svg(scene):
    def ops(s):
        result = []
        for kind, a in s.ops:
            if kind == 'group':
                result.append(f'<g transform="translate({a["x"]} {a["y"]}) scale({a["scale"]})">{ops(a["scene"])}</g>')
            elif kind == 'rect':
                result.append(f'<rect x="{a["x"]}" y="{a["y"]}" width="{a["w"]}" height="{a["h"]}" rx="{a["radius"]}" fill="{a["fill"]}" stroke="{a["stroke"]}" stroke-width="{a["width"]}"/>')
            elif kind == 'circle':
                result.append(f'<circle cx="{a["x"]}" cy="{a["y"]}" r="{a["r"]}" fill="{a["fill"]}" stroke="{a["stroke"]}" stroke-width="2"/>')
            elif kind == 'text':
                result.append(f'<text x="{a["x"]}" y="{a["y"]}" font-family="Microsoft JhengHei,Noto Sans CJK TC,sans-serif" font-size="{a["size"]}" font-weight="{700 if a["bold"] else 400}" fill="{a["color"]}" text-anchor="{a["anchor"]}">{escape(a["value"])}</text>')
            elif kind == 'line':
                pts = ' '.join(f'{x},{y}' for x,y in a['points'])
                if a['halo']:
                    result.append(f'<polyline points="{pts}" fill="none" stroke="white" stroke-width="{a["width"]+3}"/>')
                dash = ' stroke-dasharray="7 5"' if a['dashed'] else ''
                result.append(f'<polyline points="{pts}" fill="none" stroke="{a["color"]}" stroke-width="{a["width"]}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')
        return '\n'.join(result)
    return f'<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="{scene.w}" height="{scene.h}" viewBox="0 0 {scene.w} {scene.h}">\n{ops(scene)}\n</svg>'

def render_pdf(scene, doc):
    height = scene.h
    for kind, a in scene.ops:
        if kind == 'group':
            doc.saveState()
            if a.get('clip'):
                x,y,w,h=a['clip']
                clip_path=doc.beginPath(); clip_path.rect(x,height-y-h,w,h)
                doc.clipPath(clip_path,stroke=0,fill=0)
            doc.translate(a['x'], height-a['y']-a['scene'].h*a['scale'])
            doc.scale(a['scale'], a['scale'])
            render_pdf(a['scene'], doc)
            doc.restoreState()
        elif kind == 'text':
            doc.setFillColor(HexColor(a['color']))
            doc.setFont('CJKB' if a['bold'] else 'CJK', a['size'])
            draw = {'start': doc.drawString, 'end': doc.drawRightString, 'middle': doc.drawCentredString}[a['anchor']]
            draw(a['x'], height-a['y'], a['value'])
        elif kind == 'rect':
            doc.setLineWidth(a['width'])
            if a['fill'] != 'none': doc.setFillColor(HexColor(a['fill']))
            if a['stroke'] != 'none': doc.setStrokeColor(HexColor(a['stroke']))
            doc.roundRect(a['x'], height-a['y']-a['h'], a['w'], a['h'], a['radius'],
                          fill=a['fill']!='none', stroke=a['stroke']!='none')
        elif kind == 'circle':
            doc.setFillColor(HexColor(a['fill'])); doc.setStrokeColor(HexColor(a['stroke'])); doc.setLineWidth(1.7)
            doc.circle(a['x'], height-a['y'], a['r'], stroke=1, fill=1)
        elif kind == 'line':
            doc.setLineCap(1); doc.setLineJoin(1)
            path = doc.beginPath()
            path.moveTo(a['points'][0][0], height-a['points'][0][1])
            for x,y in a['points'][1:]: path.lineTo(x, height-y)
            if a['halo']:
                doc.setDash(); doc.setStrokeColor(HexColor('white')); doc.setLineWidth(a['width']+3); doc.drawPath(path)
            doc.setStrokeColor(HexColor(a['color'])); doc.setLineWidth(a['width'])
            doc.setDash([7, 5] if a['dashed'] else [])
            doc.drawPath(path); doc.setDash()

def write_pdf(path, scenes, paper):
    doc = canvas.Canvas(str(path), pagesize=paper, pageCompression=1)
    doc.setTitle('撲克牌發牌機 V1.0.0 接線圖')
    doc.setAuthor('CardDealer project')
    for s in scenes:
        pw, ph = paper
        scale = min(pw/s.w, ph/s.h)
        doc.saveState(); doc.translate((pw-s.w*scale)/2, (ph-s.h*scale)/2); doc.scale(scale, scale)
        render_pdf(s, doc)
        doc.restoreState(); doc.showPage()
    doc.save()

def validate_fw():
    config = (ROOT / 'firmware/CardDealer/BoardConfig.h').read_text(encoding='utf8')
    for name, value in {'kFeedIn1':5, 'kFeedIn2':6, 'kEjectIn1':7, 'kExitPin':10, 'kSda':21, 'kScl':20, 'kHomePcfBit':4}.items():
        assert re.search(r'\b'+name+r'\s*=\s*'+str(value)+r'\s*;', config)
    assert re.search(r'kStepperPins\[4\]\s*=\s*\{0, 1, 3, 4\}', config)
    rows=list(csv.DictReader((ROOT / 'firmware/docs/滑環12路接線.csv').open(encoding='utf-8-sig')))
    assert len(rows)==12
    assert [int(row['路數']) for row in rows] == list(range(1,13))
    assert rows[3]['固定端']=='GPIO21' and rows[4]['固定端']=='GPIO20'
    assert rows[9]['旋轉端']=='PCF8574 P4'