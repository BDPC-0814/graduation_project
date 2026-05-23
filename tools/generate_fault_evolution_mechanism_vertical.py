from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
PNG_OUT = FIG_DIR / "面向故障演化过程的调度机制图.png"
SVG_OUT = FIG_DIR / "面向故障演化过程的调度机制图.svg"

W, H = 1500, 2200

BG = "#FFFFFF"
MODULE_FILL = "#FFFDE2"
MODULE_STROKE = "#C9C66A"
INNER_FILL = "#EEE9FF"
INNER_STROKE = "#B9ADF6"
INPUT_FILL = "#E9F0FF"
INPUT_STROKE = "#A7B8F8"
OUTPUT_FILL = "#E7F7EF"
OUTPUT_STROKE = "#7CC7A0"
INK = "#1F2937"
MUTED = "#64748B"
ARROW = "#111827"
ACCENT = "#0F766E"
FEEDBACK = "#B45309"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc") if bold else Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


F_TITLE = font(40, True)
F_SUB = font(22)
F_HEAD = font(24, True)
F_BOX = font(24)
F_NOTE = font(19)


def rect(draw: ImageDraw.ImageDraw, box, fill: str, outline: str, radius: int = 0, width: int = 2) -> None:
    if radius:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    else:
        draw.rectangle(box, fill=fill, outline=outline, width=width)


def center(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill: str = INK, spacing: int = 7) -> None:
    lines = text.split("\n")
    sizes = [draw.textbbox((0, 0), line, font=fnt) for line in lines]
    widths = [b[2] - b[0] for b in sizes]
    heights = [b[3] - b[1] for b in sizes]
    total_h = sum(heights) + (len(lines) - 1) * spacing
    x1, y1, x2, y2 = box
    y = y1 + ((y2 - y1) - total_h) / 2
    for line, tw, th in zip(lines, widths, heights):
        x = x1 + ((x2 - x1) - tw) / 2
        draw.text((x, y), line, font=fnt, fill=fill)
        y += th + spacing


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = ARROW, width: int = 4) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        d = 1 if x2 >= x1 else -1
        pts = [(x2, y2), (x2 - d * 18, y2 - 9), (x2 - d * 18, y2 + 9)]
    else:
        d = 1 if y2 >= y1 else -1
        pts = [(x2, y2), (x2 - 9, y2 - d * 18), (x2 + 9, y2 - d * 18)]
    draw.polygon(pts, fill=color)


def draw_module(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, items: list[str]) -> tuple[int, int, int, int]:
    outer = (x, y, x + w, y + h)
    rect(draw, outer, MODULE_FILL, MODULE_STROKE, width=2)
    center(draw, (x + 16, y + 18, x + w - 16, y + 58), title, F_HEAD, ACCENT)

    item_w = 240
    item_h = 88
    gap = 30
    total_w = len(items) * item_w + (len(items) - 1) * gap
    start_x = x + (w - total_w) // 2
    cy = y + 105
    for i, item in enumerate(items):
        ibox = (start_x + i * (item_w + gap), cy, start_x + i * (item_w + gap) + item_w, cy + item_h)
        rect(draw, ibox, INNER_FILL, INNER_STROKE, width=2)
        center(draw, ibox, item, F_BOX)
    return outer


MODULES = [
    ("快线采集与运行反馈模块", ["采集快线字段", "读取边端反馈", "识别设备不可用"]),
    ("三类控制量计算模块", ["紧迫度\nUrgency", "字段优先级\nField Priority", "执行压力\nExecution Pressure", "综合控制分\nControl Score"]),
    ("相位驱动调度模块", ["聚焦采样\nFOCUS", "恢复观测\nRECOVERY", "巡航巡检\nCRUISE", "边端降级\nDEGRADED"]),
    ("字段与传输策略模块", ["选择采样间隔\ninterval", "确定快/慢字段策略", "确定上传/缓冲策略"]),
    ("边端可靠执行模块", ["快慢字段合并", "RingBuffer 吸峰", "SQLite WAL 持久化", "异步上传/失败重试"]),
]


def draw_png() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 42), "面向故障演化过程的调度机制图", font=F_TITLE, fill=INK)
    draw.text(
        (70, 96),
        "以快线指标和边端反馈为输入，纵向串联风险计算、相位调度、字段策略与可靠执行，形成闭环采样控制。",
        font=F_SUB,
        fill=MUTED,
    )

    input_box = (70, 185, 315, 290)
    rect(draw, input_box, INPUT_FILL, INPUT_STROKE, width=2)
    center(draw, input_box, "异构设备\n快线指标", F_BOX)

    x, w, h = 370, 880, 245
    y0, gap = 165, 90
    boxes = []
    for idx, (title, items) in enumerate(MODULES):
        boxes.append(draw_module(draw, x, y0 + idx * (h + gap), w, h, title, items))

    output_box = (1180, 1910, 1425, 2015)
    rect(draw, output_box, OUTPUT_FILL, OUTPUT_STROKE, width=2)
    center(draw, output_box, "统一XPU\n时序数据模型", F_BOX)

    arrow(draw, (315, 238), (370, 238))
    for upper, lower in zip(boxes, boxes[1:]):
        arrow(draw, ((upper[0] + upper[2]) // 2, upper[3]), ((lower[0] + lower[2]) // 2, lower[1]))
    arrow(draw, ((boxes[-1][0] + boxes[-1][2]) // 2, boxes[-1][3]), (1180, 1962))

    # Key callouts
    callouts = [
        (90, 520, 310, 100, "快字段：util / temp / power\nstatus / error"),
        (90, 855, 310, 100, "慢字段：freq / ECC / PCIe\nthreads / cache / reset"),
        (90, 1190, 310, 100, "输出：interval + phase\nfield_policy + transport_policy"),
    ]
    for cx, cy, cw, ch, text in callouts:
        rect(draw, (cx, cy, cx + cw, cy + ch), "#FFFFFF", "#CBD5E1", radius=12)
        center(draw, (cx + 8, cy + 5, cx + cw - 8, cy + ch - 5), text, F_NOTE, MUTED)

    # Feedback loop on the right side.
    draw.line((1265, 1740, 1365, 1740, 1365, 360, 1250, 360), fill=FEEDBACK, width=5)
    draw.polygon([(1250, 360), (1272, 348), (1272, 372)], fill=FEEDBACK)
    center(
        draw,
        (930, 2035, 1410, 2105),
        "运行反馈闭环：outbox积压 / 失信数量 / 环形缓冲压力 / 上传状态",
        F_NOTE,
        FEEDBACK,
    )
    draw.line((1120, 2018, 1365, 2018, 1365, 1740), fill=FEEDBACK, width=5)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT)


def svg_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str, rx: int = 0, width: int = 2) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def svg_text(x: int, y: int, text: str, size: int, color: str = INK, weight: str = "400") -> str:
    return f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(text)}</text>'


def draw_svg() -> None:
    # Keep an editable vector companion. The PNG is the primary PPT asset.
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        svg_text(70, 82, "面向故障演化过程的调度机制图", 40, INK, "700"),
        svg_text(70, 128, "以快线指标和边端反馈为输入，纵向串联风险计算、相位调度、字段策略与可靠执行，形成闭环采样控制。", 22, MUTED),
        "</svg>",
    ]
    SVG_OUT.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    draw_png()
    draw_svg()
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {SVG_OUT}")


if __name__ == "__main__":
    main()
