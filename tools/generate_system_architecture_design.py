# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PNG_PATH = OUT_DIR / "图4_2_系统总体架构设计图.png"
SVG_PATH = OUT_DIR / "图4_2_系统总体架构设计图.svg"

W, H = 1600, 900
PRIMARY = "#1f4e79"
LIGHT = "#eef4fb"
DARK = "#111827"
MUTED = "#4b5563"
BORDER = "#cbd5e1"
ROW_FILL = "#f8fafc"
WHITE = "#ffffff"


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


F_LAYER = font(26, True)
F_HEAD = font(22, True)
F_BODY = font(20)
F_SMALL = font(18)
F_TINY = font(16)
F_NOTE = font(17)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int):
    lines = []
    for raw in text.split("\n"):
        line = ""
        for ch in raw:
            test = line + ch
            if text_size(draw, test, fnt)[0] <= max_width or not line:
                line = test
            else:
                lines.append(line)
                line = ch
        if line:
            lines.append(line)
    return lines


def draw_center_text(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    text: str,
    fnt,
    fill: str = DARK,
    max_width: Optional[int] = None,
    line_gap: int = 4,
):
    x1, y1, x2, y2 = box
    if max_width is None:
        max_width = x2 - x1 - 18
    lines = wrap_text(draw, text, fnt, max_width)
    heights = [text_size(draw, line, fnt)[1] for line in lines]
    total_h = sum(heights) + line_gap * max(len(lines) - 1, 0)
    y = y1 + (y2 - y1 - total_h) / 2
    for line, h in zip(lines, heights):
        w, _ = text_size(draw, line, fnt)
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def rect(draw: ImageDraw.ImageDraw, box, fill: str, outline: str = BORDER, width: int = 1):
    draw.rectangle(box, fill=fill, outline=outline, width=width)


def rounded(draw: ImageDraw.ImageDraw, box, fill: str, outline: str = PRIMARY, width: int = 2, radius: int = 8):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def module(
    draw: ImageDraw.ImageDraw,
    box,
    text: str,
    fill: str = PRIMARY,
    outline: Optional[str] = None,
    fnt=F_BODY,
    color: str = WHITE,
    radius: int = 0,
):
    if radius:
        rounded(draw, box, fill, outline or fill, 1, radius)
    else:
        rect(draw, box, fill, outline or fill, 1)
    draw_center_text(draw, box, text, fnt, color)


def arrow(draw: ImageDraw.ImageDraw, start, end, fill: str = PRIMARY, width: int = 4):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=fill, width=width)
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 >= x1 else -1
        pts = [(x2, y2), (x2 - sign * 18, y2 - 10), (x2 - sign * 18, y2 + 10)]
    else:
        sign = 1 if y2 >= y1 else -1
        pts = [(x2, y2), (x2 - 10, y2 - sign * 18), (x2 + 10, y2 - sign * 18)]
    draw.polygon(pts, fill=fill)


def draw_layers(draw: ImageDraw.ImageDraw):
    x0, label_w, x2 = 45, 150, W - 45
    rows = [
        ("展示控制层", 45, 190),
        ("服务支撑层", 220, 405),
        ("采样执行层", 435, 755),
    ]
    for label, y1, y2 in rows:
        rect(draw, (x0, y1, x2, y2), WHITE, BORDER, 1)
        rect(draw, (x0, y1, x0 + label_w, y2), ROW_FILL, BORDER, 1)
        draw_center_text(draw, (x0, y1, x0 + label_w, y2), label, F_LAYER)


def build_png():
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    draw_layers(draw)

    top_modules = [
        (220, 85, 485, 155, "仪表盘\n状态总览"),
        (515, 85, 780, 155, "实时趋势\n图表展示"),
        (810, 85, 1075, 155, "控制台\n任务交互"),
        (1105, 85, 1370, 155, "告警中心\n实验结果"),
    ]
    for item in top_modules:
        module(draw, item[:4], item[4])

    svc_modules = [
        (220, 285, 385, 350, "HTTP API\n服务"),
        (405, 285, 570, 350, "数据接收\n与校验"),
        (590, 285, 755, 350, "记录写入\n快照更新"),
        (775, 285, 940, 350, "规则评估\n告警联动"),
        (960, 285, 1125, 350, "查询聚合\n历史日志"),
        (1145, 285, 1310, 350, "实验任务\n编排"),
    ]
    for item in svc_modules:
        module(draw, item[:4], item[4], fnt=F_SMALL)

    rounded(draw, (1360, 285, 1525, 350), LIGHT, PRIMARY, 2)
    draw_center_text(draw, (1360, 285, 1525, 350), "SQLite\n中心数据库", F_SMALL)

    groups = [
        (220, 485, 440, 710, "设备接入适配器"),
        (470, 485, 655, 710, "统一指标建模"),
        (685, 485, 870, 710, "单设备采样器"),
        (900, 485, 1120, 710, "故障演化调度器"),
        (1150, 485, 1450, 710, "边端可靠执行"),
    ]
    for x1, y1, x2, y2, label in groups:
        rect(draw, (x1, y1, x2, y2), LIGHT, PRIMARY, 2)
        draw_center_text(draw, (x1 + 8, y1 + 14, x2 - 8, y1 + 54), label, F_HEAD, fill=PRIMARY)

    for box, text in [
        ((245, 565, 320, 610), "CPU"),
        ((340, 565, 415, 610), "GPU"),
        ((245, 635, 320, 680), "NPU"),
        ((340, 635, 415, 680), "回放"),
    ]:
        module(draw, box, text, WHITE, BORDER, F_SMALL, DARK)

    for box, text in [
        ((492, 560, 633, 610), "统一字段"),
        ((492, 635, 633, 685), "XPU对象"),
        ((707, 555, 848, 598), "快线字段"),
        ((707, 612, 848, 655), "慢线补采"),
        ((707, 669, 848, 700), "结果合并"),
        ((925, 555, 1095, 595), "紧迫度 U"),
        ((925, 608, 1095, 648), "字段优先级 F"),
        ((925, 661, 1095, 701), "执行压力 E / 控制分 C"),
        ((1180, 555, 1420, 595), "RingBuffer 缓冲"),
        ((1180, 608, 1420, 648), "SQLite WAL 持久化队列"),
        ((1180, 661, 1420, 701), "批量压缩上传 / 失败重试"),
    ]:
        rounded(draw, box, WHITE, PRIMARY, 2)
        draw_center_text(draw, box, text, F_TINY if len(text) > 10 else F_SMALL, DARK)

    y_mid = 610
    for start, end in [((440, y_mid), (470, y_mid)), ((655, y_mid), (685, y_mid)), ((870, y_mid), (900, y_mid)), ((1120, y_mid), (1150, y_mid))]:
        arrow(draw, start, end)

    arrow(draw, (1450, y_mid), (1495, y_mid))
    rounded(draw, (1495, 555, 1550, 665), LIGHT, PRIMARY, 2)
    draw_center_text(draw, (1495, 555, 1550, 665), "后端\n接收", F_TINY)

    arrow(draw, (1524, 555), (1524, 350))
    arrow(draw, (1360, 318), (1310, 318))
    arrow(draw, (1032, 285), (1032, 155))
    arrow(draw, (1075, 120), (1105, 120))

    draw.line((1300, 710, 1300, 765, 1010, 765, 1010, 710), fill=PRIMARY, width=4)
    draw.polygon([(1010, 710), (1000, 728), (1020, 728)], fill=PRIMARY)
    draw_center_text(draw, (770, 785, 1320, 830), "运行反馈闭环：outbox积压 / 失败数量 / 环形缓冲压力 / 上传状态", F_NOTE, PRIMARY)

    rect(draw, (45, 840, W - 45, 875), WHITE, BORDER, 1)
    legend = [
        (220, 846, 500, 869, "异构设备状态源", LIGHT, DARK),
        (530, 846, 830, 869, "统一 XPU 时序数据模型", PRIMARY, WHITE),
        (860, 846, 1160, 869, "回放轨迹与实验报告", LIGHT, DARK),
        (1190, 846, 1495, 869, "概览 / 历史 / 日志 / 事件查询", PRIMARY, WHITE),
    ]
    for x1, y1, x2, y2, text, fill, color in legend:
        module(draw, (x1, y1, x2, y2), text, fill, fill, F_TINY, color)

    img.save(PNG_PATH)


def svg_text(x, y, text, size=20, weight="normal", fill=DARK, anchor="middle"):
    lines = text.split("\n")
    out = [f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">']
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else size + 5
        out.append(f'<tspan x="{x}" dy="{dy}">{line}</tspan>')
    out.append("</text>")
    return "\n".join(out)


def svg_rect(x, y, w, h, fill, stroke=BORDER, sw=1, rx=0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def svg_center(x, y, w, h, text, size=20, weight="normal", fill=DARK):
    line_count = text.count("\n") + 1
    top_y = y + h / 2 - ((line_count - 1) * (size + 5)) / 2 + size * 0.35
    return svg_text(x + w / 2, top_y, text, size, weight, fill)


def svg_arrow(x1, y1, x2, y2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{PRIMARY}" stroke-width="4" marker-end="url(#arrow)"/>'


def svg_module(x, y, w, h, text, fill=PRIMARY, stroke=None, size=20, color=WHITE, rx=0):
    return svg_rect(x, y, w, h, fill, stroke or fill, 1, rx) + "\n" + svg_center(x, y, w, h, text, size, fill=color)


def build_svg():
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="{PRIMARY}"/></marker></defs>',
        '<style>text{font-family:"Microsoft YaHei","SimHei",Arial,sans-serif}</style>',
        f'<rect width="{W}" height="{H}" fill="{WHITE}"/>',
    ]

    for label, y1, y2 in [("展示控制层", 45, 190), ("服务支撑层", 220, 405), ("采样执行层", 435, 755)]:
        parts.append(svg_rect(45, y1, 1510, y2 - y1, WHITE))
        parts.append(svg_rect(45, y1, 150, y2 - y1, ROW_FILL))
        parts.append(svg_center(45, y1, 150, y2 - y1, label, 26, "700", DARK))

    for x, text in [(220, "仪表盘\n状态总览"), (515, "实时趋势\n图表展示"), (810, "控制台\n任务交互"), (1105, "告警中心\n实验结果")]:
        parts.append(svg_module(x, 85, 265, 70, text))

    for x, text in [(220, "HTTP API\n服务"), (405, "数据接收\n与校验"), (590, "记录写入\n快照更新"), (775, "规则评估\n告警联动"), (960, "查询聚合\n历史日志"), (1145, "实验任务\n编排")]:
        parts.append(svg_module(x, 285, 165, 65, text, size=18))
    parts.append(svg_rect(1360, 285, 165, 65, LIGHT, PRIMARY, 2, 8))
    parts.append(svg_center(1360, 285, 165, 65, "SQLite\n中心数据库", 18, fill=DARK))

    groups = [
        (220, 485, 220, 225, "设备接入适配器"),
        (470, 485, 185, 225, "统一指标建模"),
        (685, 485, 185, 225, "单设备采样器"),
        (900, 485, 220, 225, "故障演化调度器"),
        (1150, 485, 300, 225, "边端可靠执行"),
    ]
    for x, y, w, h, label in groups:
        parts.append(svg_rect(x, y, w, h, LIGHT, PRIMARY, 2))
        parts.append(svg_center(x, y + 14, w, 40, label, 22, "700", PRIMARY))

    for x, y, text in [(245, 565, "CPU"), (340, 565, "GPU"), (245, 635, "NPU"), (340, 635, "回放")]:
        parts.append(svg_module(x, y, 75, 45, text, WHITE, BORDER, 18, DARK))

    for x, y, w, h, text in [
        (492, 560, 141, 50, "统一字段"),
        (492, 635, 141, 50, "XPU对象"),
        (707, 555, 141, 43, "快线字段"),
        (707, 612, 141, 43, "慢线补采"),
        (707, 669, 141, 31, "结果合并"),
        (925, 555, 170, 40, "紧迫度 U"),
        (925, 608, 170, 40, "字段优先级 F"),
        (925, 661, 170, 40, "执行压力 E / 控制分 C"),
        (1180, 555, 240, 40, "RingBuffer 缓冲"),
        (1180, 608, 240, 40, "SQLite WAL 持久化队列"),
        (1180, 661, 240, 40, "批量压缩上传 / 失败重试"),
    ]:
        parts.append(svg_rect(x, y, w, h, WHITE, PRIMARY, 2, 8))
        parts.append(svg_center(x, y, w, h, text, 16 if len(text) > 10 else 18, fill=DARK))

    for x1, x2 in [(440, 470), (655, 685), (870, 900), (1120, 1150), (1450, 1495)]:
        parts.append(svg_arrow(x1, 610, x2, 610))
    parts.append(svg_rect(1495, 555, 55, 110, LIGHT, PRIMARY, 2, 8))
    parts.append(svg_center(1495, 555, 55, 110, "后端\n接收", 16, fill=DARK))

    parts.append(svg_arrow(1524, 555, 1524, 350))
    parts.append(svg_arrow(1360, 318, 1310, 318))
    parts.append(svg_arrow(1032, 285, 1032, 155))
    parts.append(svg_arrow(1075, 120, 1105, 120))
    parts.append(f'<polyline points="1300,710 1300,765 1010,765 1010,710" fill="none" stroke="{PRIMARY}" stroke-width="4" marker-end="url(#arrow)"/>')
    parts.append(svg_text(1045, 815, "运行反馈闭环：outbox积压 / 失败数量 / 环形缓冲压力 / 上传状态", 17, fill=PRIMARY))

    parts.append(svg_rect(45, 840, 1510, 35, WHITE))
    for x, text, fill, color, w in [
        (220, "异构设备状态源", LIGHT, DARK, 280),
        (530, "统一 XPU 时序数据模型", PRIMARY, WHITE, 300),
        (860, "回放轨迹与实验报告", LIGHT, DARK, 300),
        (1190, "概览 / 历史 / 日志 / 事件查询", PRIMARY, WHITE, 305),
    ]:
        parts.append(svg_module(x, 846, w, 23, text, fill, fill, 16, color))

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    build_png()
    build_svg()
    print(PNG_PATH)
    print(SVG_PATH)
