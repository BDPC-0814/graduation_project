from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
PNG_OUT = FIG_DIR / "fault_evolution_algorithm_design_cn_vertical.png"
SVG_OUT = FIG_DIR / "fault_evolution_algorithm_design_cn_vertical.svg"

W, H = 1600, 2200

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
F_MODULE_TITLE = font(26, True)
F_BOX = font(23)
F_NOTE = font(19)
F_FEEDBACK = font(28, True)


def rect(draw: ImageDraw.ImageDraw, box, fill: str, outline: str, radius: int = 0, width: int = 2) -> None:
    if radius:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    else:
        draw.rectangle(box, fill=fill, outline=outline, width=width)


def center_text(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill: str = INK, spacing: int = 7) -> None:
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
    box = (x, y, x + w, y + h)
    rect(draw, box, MODULE_FILL, MODULE_STROKE, width=2)
    center_text(draw, (x + 20, y + 18, x + w - 20, y + 62), title, F_MODULE_TITLE, ACCENT)

    item_w = 230
    item_h = 90
    gap = 28
    total_w = len(items) * item_w + (len(items) - 1) * gap
    start_x = x + (w - total_w) // 2
    item_y = y + 102
    for idx, item in enumerate(items):
        ix = start_x + idx * (item_w + gap)
        ibox = (ix, item_y, ix + item_w, item_y + item_h)
        rect(draw, ibox, INNER_FILL, INNER_STROKE, width=2)
        center_text(draw, ibox, item, F_BOX)
    return box


MODULES = [
    ("第一步：基线更新", ["读取观测值\nx(t)", "EMA 更新基线\nB(t)", "FOCUS/RECOVERY\n降低 α", "输出利用率/温度\n功耗基线"]),
    ("第二步：控制量计算", ["紧迫度 U\nUrgency", "字段优先级 F\nField Priority", "执行压力 E\nExecution Pressure", "综合控制分 C\nControl Score"]),
    ("第三步：相位判定", ["聚焦采样\nFOCUS", "边端降级\nDEGRADED", "恢复观测\nRECOVERY", "巡航巡检\nCRUISE"]),
    ("第四步：策略输出", ["计算下次间隔\nt_next", "确定快/慢线\n字段策略", "确定直传/缓冲\n传输策略", "生成采样决策\nDecision"]),
    ("边端执行与反馈", ["快慢字段采集\n与记录合并", "RingBuffer 吸峰", "SQLite WAL/outbox\n持久化", "上传状态与积压\n反馈下一轮"]),
]


def draw_png() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 42), "故障演化采样系统算法设计图", font=F_TITLE, fill=INK)
    draw.text(
        (70, 96),
        "核心思路：基线更新 → 控制量计算 → 相位判定 → 策略输出，边端执行结果再反馈到下一轮调度。",
        font=F_SUB,
        fill=MUTED,
    )

    input_box = (70, 185, 320, 295)
    rect(draw, input_box, INPUT_FILL, INPUT_STROKE, width=2)
    center_text(draw, input_box, "异构设备\n观测值与反馈", F_BOX)

    x, w, h = 380, 1040, 220
    y0, gap = 165, 105
    boxes = []
    for idx, (title, items) in enumerate(MODULES):
        boxes.append(draw_module(draw, x, y0 + idx * (h + gap), w, h, title, items))

    output_box = (1145, 1910, 1460, 2030)
    rect(draw, output_box, OUTPUT_FILL, OUTPUT_STROKE, width=2)
    center_text(draw, output_box, "统一XPU时序模型\n指标/事件/策略上下文", F_BOX)

    arrow(draw, (320, 240), (380, 240))
    cx = x + w // 2
    for upper, lower in zip(boxes, boxes[1:]):
        arrow(draw, (cx, upper[3]), (cx, lower[1]))
    arrow(draw, (cx, boxes[-1][3]), (1145, 1970))

    # Feedback loop is routed outside the yellow modules to avoid visual collision.
    feedback_x = 1510
    first_right, first_mid_y = boxes[0][2], (boxes[0][1] + boxes[0][3]) // 2
    edge_right, edge_mid_y = boxes[-1][2], (boxes[-1][1] + boxes[-1][3]) // 2
    output_right, output_mid_y = output_box[2], (output_box[1] + output_box[3]) // 2

    draw.line(
        (edge_right, edge_mid_y, feedback_x, edge_mid_y, feedback_x, first_mid_y, first_right, first_mid_y),
        fill=FEEDBACK,
        width=5,
    )
    draw.polygon(
        [(first_right, first_mid_y), (first_right + 22, first_mid_y - 12), (first_right + 22, first_mid_y + 12)],
        fill=FEEDBACK,
    )
    draw.line((output_right, output_mid_y, feedback_x, output_mid_y, feedback_x, edge_mid_y), fill=FEEDBACK, width=5)

    feedback_text = "运行反馈闭环：outbox积压 / 死信数量 / 环形缓冲压力 / 上传状态"
    ty = 505
    for ch in feedback_text:
        if ch == " ":
            ty += 10
            continue
        bbox = draw.textbbox((0, 0), ch, font=F_NOTE)
        draw.text((1530 + (24 - (bbox[2] - bbox[0])) / 2, ty), ch, font=F_NOTE, fill=FEEDBACK)
        ty += 25

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT)


def svg_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str, rx: int = 0, width: int = 2) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def svg_text(x: int, y: int, text: str, size: int, color: str = INK, weight: str = "400") -> str:
    return f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(text)}</text>'


def draw_svg() -> None:
    # Editable companion with the same canvas and main blocks; PNG is the polished asset.
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        svg_text(70, 82, "故障演化采样系统算法设计图", 40, INK, "700"),
        svg_text(70, 128, "核心思路：基线更新 → 控制量计算 → 相位判定 → 策略输出，边端执行结果再反馈到下一轮调度。", 22, MUTED),
    ]
    for idx, (title, items) in enumerate(MODULES):
        x, y, w, h = 380, 165 + idx * (220 + 105), 1040, 220
        parts.append(svg_rect(x, y, w, h, MODULE_FILL, MODULE_STROKE))
        parts.append(svg_text(x + 390, y + 54, title, 26, ACCENT, "700"))
        item_w, item_h, gap = 230, 90, 28
        total = len(items) * item_w + (len(items) - 1) * gap
        sx = x + (w - total) // 2
        for i, item in enumerate(items):
            ix = sx + i * (item_w + gap)
            parts.append(svg_rect(ix, y + 102, item_w, item_h, INNER_FILL, INNER_STROKE))
            for j, line in enumerate(item.split("\n")):
                parts.append(svg_text(ix + 28, y + 140 + j * 27, line, 21, INK))
    parts.append("</svg>")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    draw_png()
    draw_svg()
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {SVG_OUT}")


if __name__ == "__main__":
    main()
