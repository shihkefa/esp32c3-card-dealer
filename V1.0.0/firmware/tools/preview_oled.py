"""Render sample screens using the exact bitmap table shipped in Font16.h."""
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageFont


def render_preview(destination: Path) -> dict:
    root = Path(__file__).resolve().parents[1]
    header = (root / 'CardDealer/Font16.h').read_text(encoding='utf8')

    def values(name: str) -> list[int]:
        body = re.search(r'\b' + name + r'[^=]*=\s*\{(.*?)\};', header, re.S).group(1)
        return [int(v, 16) for v in re.findall(r'0x([0-9A-Fa-f]+)', body)]

    ascii_data, codes, cjk_data = values('kAscii16'), values('kCjkCodes'), values('kCjk16')
    assert len(ascii_data) == 95 * 16 and len(cjk_data) == len(codes) * 32
    glyphs = {cp: (8, ascii_data[(cp - 32) * 16:(cp - 31) * 16]) for cp in range(32, 127)}
    glyphs.update({cp: (16, cjk_data[i * 32:(i + 1) * 32]) for i, cp in enumerate(codes)})
    required = set()
    for source in (root / 'CardDealer').iterdir():
        if source.suffix in {'.h', '.cpp', '.ino'} and source.name != 'Font16.h':
            required.update(map(ord, re.findall(r'[\u3400-\u9fff]', source.read_text(encoding='utf8'))))
    assert required <= set(codes), 'Missing UI glyphs'

    def text(frame, x, y, value):
        for ch in value:
            width, data = glyphs[ord(ch)]
            for row in range(16):
                for column in range(width):
                    if data[row * (width // 8) + column // 8] & (0x80 >> (column % 8)):
                        if 0 <= x + column < 128 and 0 <= y + row < 64:
                            frame.putpixel((x + column, y + row), (128, 221, 255))
            x += width

    examples = [
        ('LANDLORD - READY', [(0, 0, '鬥地主 0/54'), (0, 16, '>'), (10, 16, '每人張數 17'),
                               (10, 32, '玩家人數 3'), (10, 48, '餘牌張數 3')]),
        ('GUANDAN - DEALING', [(0, 0, '發牌 32/108'), (10, 16, '每人張數 27'),
                                (10, 32, '玩家人數 4'), (10, 48, '餘牌張數 0')]),
        ('FIRST-USE CALIBRATION', [(0, 0, '校正 2/4'), (0, 16, '請先清空牌倉'),
                                    (0, 32, '約需一至二分'), (0, 48, '開始鍵可取消')]),
        ('FAULT - CARD STUCK', [(0, 0, '故障 E05'), (0, 16, '卡牌請清出口'),
                                 (0, 32, '清牌後按開始'), (0, 48, '重置後再發牌')]),
    ]
    result = Image.new('RGB', (1088, 648), '#111a25')
    draw = ImageDraw.Draw(result)
    caption_font = ImageFont.load_default(size=17)
    for i, (label, lines) in enumerate(examples):
        x, y = 24 + (i % 2) * 536, 16 + (i // 2) * 320
        draw.text((x, y), label, fill='#e2eaf5', font=caption_font)
        frame = Image.new('RGB', (128, 64), '#02080d')
        for tx, ty, value in lines:
            text(frame, tx, ty, value)
        result.paste(frame.resize((512, 256), Image.Resampling.NEAREST), (x, y + 32))
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.save(destination)
    return {'cjk_glyphs': len(codes), 'ascii_glyphs': 95, 'missing_ui_glyphs': 0}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    print(render_preview(root / 'docs/OLED操作預覽.png'))
