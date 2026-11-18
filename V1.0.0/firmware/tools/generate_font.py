"""Rasterize only the UI glyphs; no font file is included in the firmware."""
from pathlib import Path
import re
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1];src=root/'CardDealer'
chars=set()
for p in src.iterdir():
    if p.suffix in {'.cpp','.h','.ino'} and p.name!='Font16.h':
        chars.update(re.findall(r'[\u3400-\u9fff]',p.read_text(encoding='utf8')))
chars=sorted(chars)
cjk=ImageFont.truetype('C:/Windows/Fonts/msjh.ttc',16)
ascii_font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',14)
def bitmap(ch,font,width):
    im=Image.new('L',(width,16));ImageDraw.Draw(im).text((0,0),ch,font=font,fill=255,anchor='lt')
    out=[]
    for y in range(16):
        for b in range(width//8):
            out.append(sum((1<<(7-x)) for x in range(8) if im.getpixel((b*8+x,y))>=96))
    return out
def array(values):return '{'+','.join('0x%02X'%v for v in values)+'}'
header=['#pragma once','#include <Arduino.h>','// Generated bitmap subset for this local prototype; no original font file embedded.',
        'static const uint8_t kAscii16[95][16] PROGMEM = {']
header += [array(bitmap(chr(v),ascii_font,8))+',' for v in range(32,127)]
header += ['};',f'static constexpr unsigned kCjkCount={len(chars)};',
           'static const uint16_t kCjkCodes[] PROGMEM = {'+','.join('0x%04X'%ord(ch) for ch in chars)+'};',
           'static const uint8_t kCjk16[][32] PROGMEM = {']
header += [array(bitmap(ch,cjk,16))+', // '+ch for ch in chars]
header += ['};','']
(src/'Font16.h').write_text('\n'.join(header),encoding='utf8')
print(f'Generated {len(chars)} CJK glyphs and 95 ASCII glyphs')
