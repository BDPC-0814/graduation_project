from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
PNG_OUT = FIG_DIR / "fault_evolution_algorithm_design_cn.png"
SVG_OUT = FIG_DIR / "fault_evolution_algorithm_design_cn.svg"
THESIS_PNG_OUT = FIG_DIR / "图5-5  故障演化采样系统算法设计图.png"


W, H = 2600, 1000

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


F_TITLE = font(34, True)
F_MODULE_TITLE = font(26, True)
F_BOX = font(24)
F_SMALL = font(20)
F_NOTE = font(18)
F_FEEDBACK = font(30, True)


def center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill: str = INK,
) -> None:
    lines = text.split("\n")
    line_sizes = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=fnt)
        line_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))
    total_h = sum(h for _, h in line_sizes) + (len(lines) - 1) * 7
    y = box[1] + ((box[3] - box[1]) - total_h) / 2
    for line, (tw, th) in zip(lines, line_sizes):
        x = box[0] + ((box[2] - box[0]) - tw) / 2
        draw.text((x, y), line, font=fnt, fill=fill)
        y += th + 7


def rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str,
    radius: int = 0,
    width: int = 2,
) -> None:
    if radius:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    else:
        draw.rectangle(box, fill=fill, outline=outline, width=width)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = ARROW,
    width: int = 3,
) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 >= x1 else -1
        pts = [(x2, y2), (x2 - direction * 18, y2 - 9), (x2 - direction * 18, y2 + 9)]
    else:
        direction = 1 if y2 >= y1 else -1
        pts = [(x2, y2), (x2 - 9, y2 - direction * 18), (x2 + 9, y2 - direction * 18)]
    draw.polygon(pts, fill=color)


def draw_module(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    items: list[str],
) -> tuple[int, int, int, int]:
    outer = (x, y, x + w, y + h)
    rect(draw, outer, fill=MODULE_FILL, outline=MODULE_STROKE, width=2)
    center_text(draw, (x + 10, y + 12, x + w - 10, y + 60), title, F_MODULE_TITLE, ACCENT)

    item_h = 72 if len(items) >= 4 else 78
    gap = 28 if len(items) >= 4 else 34
    total = len(items) * item_h + (len(items) - 1) * gap
    cy = y + 75 + max(0, (h - 98 - total) // 2)
    for item in items:
        ibox = (x + 45, cy, x + w - 45, cy + item_h)
        rect(draw, ibox, fill=INNER_FILL, outline=INNER_STROKE, width=2)
        center_text(draw, ibox, item, F_BOX)
        cy += item_h + gap
    return outer


MODULES = [
    (
        300,
        170,
        340,
        555,
        "第一步：基线更新",
        ["读取观测值\nx(t)", "EMA 更新基线\nB(t)", "FOCUS/RECOVERY\n降低 α", "输出利用率/温度\n功耗基线"],
    ),
    (
        700,
        170,
        340,
        555,
        "第二步：控制量计算",
        ["紧迫度 U\nUrgency", "字段优先级 F\nField Priority", "执行压力 E\nExecution Pressure", "综合控制分 C\nControl Score"],
    ),
    (
        1100,
        170,
        340,
        555,
        "第三步：相位判定",
        ["聚焦采样\nFOCUS", "边端降级\nDEGRADED", "恢复观测\nRECOVERY", "巡航巡检\nCRUISE"],
    ),
    (
        1500,
        170,
        340,
        555,
        "第四步：策略输出",
        ["计算下次间隔\nt_next", "确定快/慢线\n字段策略", "确定直传/缓冲\n传输策略", "生成采样决策\nDecision"],
    ),
    (
        1900,
        170,
        360,
        555,
        "边端执行与反馈",
        ["快慢字段采集\n与记录合并", "RingBuffer 吸峰", "SQLite WAL/outbox\n持久化", "上传状态与积压\n反馈下一轮"],
    ),
]

def draw_png() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 34), "故障演化采样系统算法设计图", font=F_TITLE, fill=INK)
    draw.text(
        (70, 82),
        "核心思路：基线更新 → 控制量计算 → 相位判定 → 策略输出，边端执行结果再反馈到下一轮调度。",
        font=F_SMALL,
        fill=MUTED,
    )

    input_box = (45, 360, 245, 450)
    rect(draw, input_box, fill=INPUT_FILL, outline=INPUT_STROKE, width=2)
    center_text(draw, input_box, "异构设备\n观测值与反馈", F_BOX)

    boxes = [draw_module(draw, *module) for module in MODULES]

    output_box = (2325, 350, 2555, 460)
    rect(draw, output_box, fill=OUTPUT_FILL, outline=OUTPUT_STROKE, width=2)
    center_text(draw, output_box, "统一XPU时序模型\n指标/事件/策略上下文", F_SMALL)

    arrow(draw, (245, 405), (310, 405))
    for left, right in zip(boxes, boxes[1:]):
        arrow(draw, (left[2], 405), (right[0], 405))
    arrow(draw, (boxes[-1][2], 405), (output_box[0], 405))

    draw.line((2100, 735, 2100, 905, 470, 905, 470, 725), fill=FEEDBACK, width=4)
    draw.polygon([(470, 725), (458, 746), (482, 746)], fill=FEEDBACK)
    feedback_text = "运行反馈闭环：outbox积压 / 死信数量 / 环形缓冲压力 / 上传状态"
    fb = draw.textbbox((0, 0), feedback_text, font=F_FEEDBACK)
    draw.text(((W - (fb[2] - fb[0])) / 2, 864), feedback_text, font=F_FEEDBACK, fill=FEEDBACK)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT)
    img.save(THESIS_PNG_OUT)


def svg_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str, rx: int = 0) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def svg_text_center(
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    size: int = 22,
    color: str = INK,
    weight: str = "400",
) -> str:
    lines = text.split("\n")
    line_h = size * 1.25
    start_y = y + h / 2 - (len(lines) - 1) * line_h / 2 + size * 0.35
    parts = []
    for i, line in enumerate(lines):
        parts.append(
            f'<text x="{x + w / 2}" y="{start_y + i * line_h}" text-anchor="middle" '
            f'font-family="Microsoft YaHei, Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(line)}</text>'
        )
    return "\n".join(parts)


def svg_arrow(x1: int, y1: int, x2: int, y2: int, color: str = ARROW) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3" marker-end="url(#arrow)"/>'


def draw_svg() -> None:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
        '<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">',
        f'<path d="M2,2 L10,6 L2,10 Z" fill="{ARROW}"/>',
        "</marker>",
        '<marker id="arrowFeedback" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">',
        f'<path d="M2,2 L10,6 L2,10 Z" fill="{FEEDBACK}"/>',
        "</marker>",
        "</defs>",
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        '<text x="70" y="68" font-family="Microsoft YaHei, Arial" font-size="34" font-weight="700" fill="#1F2937">故障演化采样系统算法设计图</text>',
        '<text x="70" y="110" font-family="Microsoft YaHei, Arial" font-size="20" fill="#64748B">核心思路：基线更新 → 控制量计算 → 相位判定 → 策略输出，边端执行结果再反馈到下一轮调度。</text>',
    ]

    parts.append(svg_rect(45, 360, 200, 90, INPUT_FILL, INPUT_STROKE))
    parts.append(svg_text_center(45, 360, 200, 90, "异构设备\n观测值与反馈", 24))

    boxes = []
    for x, y, w, h, title, items in MODULES:
        boxes.append((x, y, x + w, y + h))
        parts.append(svg_rect(x, y, w, h, MODULE_FILL, MODULE_STROKE))
        parts.append(svg_text_center(x + 10, y + 12, w - 20, 48, title, 26, ACCENT, "700"))

        item_h = 72 if len(items) >= 4 else 78
        gap = 28 if len(items) >= 4 else 34
        total = len(items) * item_h + (len(items) - 1) * gap
        cy = y + 75 + max(0, (h - 98 - total) // 2)
        for item in items:
            parts.append(svg_rect(x + 45, cy, w - 90, item_h, INNER_FILL, INNER_STROKE))
            parts.append(svg_text_center(x + 45, cy, w - 90, item_h, item, 23))
            cy += item_h + gap

    parts.append(svg_rect(2325, 350, 230, 110, OUTPUT_FILL, OUTPUT_STROKE))
    parts.append(svg_text_center(2325, 350, 230, 110, "统一XPU时序模型\n指标/事件/策略上下文", 20))
    parts.append(svg_arrow(245, 405, 310, 405))
    for left, right in zip(boxes, boxes[1:]):
        parts.append(svg_arrow(left[2], 405, right[0], 405))
    parts.append(svg_arrow(boxes[-1][2], 405, 2325, 405))

    parts.append(
        f'<path d="M2100,735 L2100,905 L470,905 L470,725" fill="none" stroke="{FEEDBACK}" stroke-width="4" marker-end="url(#arrowFeedback)"/>'
    )
    parts.append(
        f'<text x="{W / 2}" y="892" text-anchor="middle" font-family="Microsoft YaHei, Arial" font-size="30" font-weight="700" fill="{FEEDBACK}">运行反馈闭环：outbox积压 / 死信数量 / 环形缓冲压力 / 上传状态</text>'
    )

    parts.append("</svg>")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    draw_png()
    draw_svg()
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {SVG_OUT}")
    print(f"Wrote {THESIS_PNG_OUT}")


if __name__ == "__main__":
    main()
