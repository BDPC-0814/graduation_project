# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PNG_PATH = OUT_DIR / "图4_4_系统_E-R_图.png"
SVG_PATH = OUT_DIR / "图4_4_系统_E-R_图.svg"

W, H = 1900, 1120
BLUE = "#18aee2"
LINE = "#1d2cff"
DARK = "#111827"
MUTED = "#4b5563"
FRAME = "#9ca3af"
WEAK = "#64748b"


def font(size: int, bold: bool = False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


F_ENTITY = font(25, True)
F_ATTR = font(20)
F_REL = font(20, True)
F_LABEL = font(18, True)
F_FRAME = font(20, True)
F_NOTE = font(17)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def draw_center_text(
    draw: ImageDraw.ImageDraw,
    box: Tuple[float, float, float, float],
    text: str,
    fnt,
    fill: str = DARK,
    line_gap: int = 4,
):
    x1, y1, x2, y2 = box
    lines = text.split("\n")
    sizes = [text_size(draw, line, fnt) for line in lines]
    total_h = sum(h for _, h in sizes) + line_gap * (len(lines) - 1)
    y = y1 + (y2 - y1 - total_h) / 2
    for line, (w, h) in zip(lines, sizes):
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def rect_from_center(cx: float, cy: float, w: float, h: float) -> Tuple[float, float, float, float]:
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    fill: str,
    width: int = 2,
    dash: int = 12,
    gap: int = 8,
):
    import math

    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        draw.line(
            (x1 + dx * pos, y1 + dy * pos, x1 + dx * end, y1 + dy * end),
            fill=fill,
            width=width,
        )
        pos = end + gap


def draw_polyline(draw: ImageDraw.ImageDraw, points: Sequence[Tuple[float, float]], fill: str, width: int = 2, dashed: bool = False):
    for start, end in zip(points, points[1:]):
        if dashed:
            draw_dashed_line(draw, start, end, fill, width=width)
        else:
            draw.line((*start, *end), fill=fill, width=width)


def draw_entity(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, label: str):
    box = rect_from_center(cx, cy, w, h)
    draw.rectangle(box, fill=BLUE, outline=DARK, width=2)
    draw_center_text(draw, box, label, F_ENTITY)


def draw_attr(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, label: str):
    box = rect_from_center(cx, cy, w, h)
    draw.ellipse(box, fill=BLUE, outline=DARK, width=2)
    draw_center_text(draw, box, label, F_ATTR)


def draw_relation(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, label: str, dashed: bool = False):
    points = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
    if dashed:
        draw.polygon(points, fill="white", outline=None)
        for start, end in zip(points, points[1:] + points[:1]):
            draw_dashed_line(draw, start, end, WEAK, width=2)
    else:
        draw.polygon(points, fill=BLUE, outline=DARK)
        draw.line((points[0], points[1], points[2], points[3], points[0]), fill=DARK, width=2)
    draw_center_text(draw, rect_from_center(cx, cy, w, h), label, F_REL)


ENTITIES = {
    "device": (650, 260, 160, 50, "设备"),
    "metric": (270, 600, 150, 50, "指标"),
    "event": (650, 790, 150, 50, "事件"),
    "alert": (1030, 600, 150, 50, "告警"),
    "rule": (1130, 260, 170, 50, "告警规则"),
    "outbox": (1620, 850, 190, 50, "发送队列记录"),
}

ATTRS = [
    ("device", 420, 120, 140, 44, "设备ID(PK)"),
    ("device", 620, 95, 120, 44, "设备类型"),
    ("device", 850, 120, 120, 44, "运行状态"),
    ("device", 395, 245, 145, 44, "最新时间戳"),
    ("device", 850, 210, 135, 44, "采样间隔"),
    ("device", 555, 370, 130, 44, "演化分数"),
    ("device", 765, 370, 130, 44, "采样相位"),
    ("metric", 90, 460, 120, 44, "指标ID(PK)"),
    ("metric", 260, 445, 110, 44, "设备ID"),
    ("metric", 460, 470, 120, 44, "采样时间"),
    ("metric", 80, 600, 110, 44, "利用率"),
    ("metric", 480, 600, 135, 44, "温度/功耗"),
    ("metric", 120, 760, 135, 44, "频率/内存"),
    ("metric", 310, 745, 130, 44, "演化分数"),
    ("metric", 510, 750, 130, 44, "调度策略"),
    ("event", 480, 675, 110, 44, "事件ID(PK)"),
    ("event", 650, 655, 110, 44, "设备ID"),
    ("event", 755, 670, 110, 44, "事件类型"),
    ("event", 480, 890, 110, 44, "严重级别"),
    ("event", 650, 930, 120, 44, "事件消息"),
    ("event", 820, 890, 110, 44, "事件来源"),
    ("event", 650, 1010, 120, 44, "创建时间"),
    ("alert", 875, 500, 110, 44, "告警ID(PK)"),
    ("alert", 1045, 485, 110, 44, "设备ID"),
    ("alert", 1210, 500, 110, 44, "规则Key"),
    ("alert", 900, 720, 110, 44, "严重级别"),
    ("alert", 1030, 750, 110, 44, "告警状态"),
    ("alert", 1220, 690, 150, 44, "首次/最近触发"),
    ("alert", 1180, 805, 120, 44, "末次值"),
    ("rule", 980, 110, 120, 44, "规则Key(PK)"),
    ("rule", 1160, 95, 120, 44, "规则标题"),
    ("rule", 1290, 120, 120, 44, "规则来源"),
    ("rule", 970, 310, 110, 44, "字段名"),
    ("rule", 1300, 255, 110, 44, "比较符"),
    ("rule", 1020, 365, 110, 44, "阈值"),
    ("rule", 1250, 365, 120, 44, "是否启用"),
    ("outbox", 1465, 735, 110, 44, "队列ID(PK)"),
    ("outbox", 1620, 720, 110, 44, "记录类型"),
    ("outbox", 1770, 735, 100, 44, "载荷"),
    ("outbox", 1460, 850, 100, 44, "状态"),
    ("outbox", 1780, 850, 110, 44, "重试次数"),
    ("outbox", 1505, 970, 130, 44, "下次重试时间"),
    ("outbox", 1620, 1000, 110, 44, "最后错误"),
    ("outbox", 1765, 970, 130, 44, "创建/更新时间"),
]

RELATIONS = [
    ("device", "metric", 430, 430, 88, 58, "产生", (520, 345, "1"), (340, 520, "N")),
    ("device", "event", 650, 520, 88, 58, "记录", (670, 390, "1"), (665, 690, "N")),
    ("device", "alert", 880, 430, 88, 58, "触发", (760, 345, "1"), (960, 520, "N")),
    ("rule", "alert", 1130, 430, 88, 58, "定义", (1145, 345, "1"), (1065, 520, "N")),
]


def entity_center(key: str) -> Tuple[float, float]:
    cx, cy, *_ = ENTITIES[key]
    return cx, cy


def render_png():
    image = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((30, 40, 1355, 1070), radius=6, outline=FRAME, width=2)
    draw.text((55, 56), "中心端 SQLite 数据库", font=F_FRAME, fill=MUTED)
    draw.rounded_rectangle((1400, 620, 1860, 1040), radius=6, outline=FRAME, width=2)
    draw.text((1425, 636), "边端本地 SQLite 数据库", font=F_FRAME, fill=MUTED)
    draw.text((1425, 666), "独立服务离线重试，不设置跨库外键", font=F_NOTE, fill=MUTED)

    # Formal E-R lines and weak outbox payload-cache hint.
    for src, dst, rx, ry, *_ in RELATIONS:
        draw.line((*entity_center(src), rx, ry), fill=LINE, width=2)
        draw.line((rx, ry, *entity_center(dst)), fill=LINE, width=2)
    draw_polyline(draw, [(720, 930), (1320, 930), (1528, 850)], WEAK, width=2, dashed=True)
    draw.text((1210, 900), "载荷缓存（非外键）", font=F_NOTE, fill=MUTED)

    for parent, ax, ay, *_ in ATTRS:
        draw.line((ax, ay, *entity_center(parent)), fill=LINE, width=2)

    for rel in RELATIONS:
        _, _, rx, ry, rw, rh, label, left_label, right_label = rel
        draw_relation(draw, rx, ry, rw, rh, label)
        for lx, ly, text in (left_label, right_label):
            draw.text((lx, ly), text, font=F_LABEL, fill=DARK)

    for key, (cx, cy, w, h, label) in ENTITIES.items():
        draw_entity(draw, cx, cy, w, h, label)

    for _, ax, ay, aw, ah, label in ATTRS:
        draw_attr(draw, ax, ay, aw, ah, label)

    image.save(PNG_PATH)


def svg_text(x: float, y: float, text: str, size: int, weight: int = 400, fill: str = DARK) -> str:
    lines = text.split("\n")
    if len(lines) == 1:
        return (
            f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}">{lines[0]}</text>'
        )
    start_y = y - (len(lines) - 1) * (size + 4) / 2
    tspans = []
    for idx, line in enumerate(lines):
        tspans.append(f'<tspan x="{x}" y="{start_y + idx * (size + 4)}">{line}</tspan>')
    return f'<text text-anchor="middle" dominant-baseline="middle" font-size="{size}" font-weight="{weight}" fill="{fill}">' + "".join(tspans) + "</text>"


def svg_rect(cx: float, cy: float, w: float, h: float, label: str) -> str:
    x, y, _, _ = rect_from_center(cx, cy, w, h)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{BLUE}" stroke="{DARK}" stroke-width="2"/>'
        + svg_text(cx, cy, label, 25, 700)
    )


def svg_attr(cx: float, cy: float, w: float, h: float, label: str) -> str:
    return (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{w / 2}" ry="{h / 2}" fill="{BLUE}" stroke="{DARK}" stroke-width="2"/>'
        + svg_text(cx, cy, label, 20)
    )


def svg_relation(cx: float, cy: float, w: float, h: float, label: str) -> str:
    points = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    return f'<polygon points="{points}" fill="{BLUE}" stroke="{DARK}" stroke-width="2"/>' + svg_text(cx, cy, label, 20, 700)


def svg_line(p1: Tuple[float, float], p2: Tuple[float, float], color: str = LINE, dashed: bool = False) -> str:
    dash = ' stroke-dasharray="12 8"' if dashed else ""
    return f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{color}" stroke-width="2"{dash}/>'


def svg_polyline(points: Sequence[Tuple[float, float]], color: str, dashed: bool = False) -> str:
    pts = " ".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="12 8"' if dashed else ""
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'


def render_svg():
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<style>text{font-family:"Microsoft YaHei","SimHei",Arial,sans-serif;}</style>',
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<rect x="30" y="40" width="1325" height="1030" rx="6" fill="none" stroke="{FRAME}" stroke-width="2"/>',
        f'<text x="55" y="76" font-size="20" font-weight="700" fill="{MUTED}">中心端 SQLite 数据库</text>',
        f'<rect x="1400" y="620" width="460" height="420" rx="6" fill="none" stroke="{FRAME}" stroke-width="2"/>',
        f'<text x="1425" y="656" font-size="20" font-weight="700" fill="{MUTED}">边端本地 SQLite 数据库</text>',
        f'<text x="1425" y="686" font-size="17" fill="{MUTED}">独立服务离线重试，不设置跨库外键</text>',
    ]

    for src, dst, rx, ry, *_ in RELATIONS:
        parts.append(svg_line(entity_center(src), (rx, ry)))
        parts.append(svg_line((rx, ry), entity_center(dst)))
    parts.append(svg_polyline([(720, 930), (1320, 930), (1528, 850)], WEAK, dashed=True))
    parts.append(f'<text x="1210" y="916" font-size="17" fill="{MUTED}">载荷缓存（非外键）</text>')

    for parent, ax, ay, *_ in ATTRS:
        parts.append(svg_line((ax, ay), entity_center(parent)))

    for rel in RELATIONS:
        _, _, rx, ry, rw, rh, label, left_label, right_label = rel
        parts.append(svg_relation(rx, ry, rw, rh, label))
        for lx, ly, text in (left_label, right_label):
            parts.append(f'<text x="{lx}" y="{ly}" font-size="18" font-weight="700" fill="{DARK}">{text}</text>')

    for cx, cy, w, h, label in ENTITIES.values():
        parts.append(svg_rect(cx, cy, w, h, label))
    for _, ax, ay, aw, ah, label in ATTRS:
        parts.append(svg_attr(ax, ay, aw, ah, label))

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    render_png()
    render_svg()
    print(PNG_PATH)
    print(SVG_PATH)
