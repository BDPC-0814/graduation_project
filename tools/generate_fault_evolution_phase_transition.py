from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
PNG_OUT = FIG_DIR / "fault_evolution_phase_transition_cn.png"
SVG_OUT = FIG_DIR / "fault_evolution_phase_transition_cn.svg"

W, H = 2000, 1120

BG = "#FFFFFF"
INK = "#1F2937"
MUTED = "#64748B"
STROKE = "#CBD5E1"
TEAL = "#0F766E"
BLUE = "#2563EB"
RED = "#B91C1C"
GREEN = "#15803D"
AMBER = "#B45309"

FILL_INPUT = "#FFFFFF"
FILL_FOCUS = "#FEE2E2"
FILL_RECOVERY = "#E8F0FF"
FILL_CRUISE = "#E7F7EF"
FILL_DEGRADED = "#FFF1D6"
FILL_NOTE = "#FFFFFF"


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
F_SUB = font(20)
F_NODE = font(27, True)
F_BODY = font(19)
F_LABEL = font(17)
F_SMALL = font(16)


def center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fnt, fill: str = INK) -> None:
    lines = text.split("\n")
    widths, heights = [], []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=fnt)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    total_h = sum(heights) + (len(lines) - 1) * 7
    y = box[1] + ((box[3] - box[1]) - total_h) / 2
    for line, tw, th in zip(lines, widths, heights):
        x = box[0] + ((box[2] - box[0]) - tw) / 2
        draw.text((x, y), line, font=fnt, fill=fill)
        y += th + 7


def rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str = STROKE, radius: int = 20, width: int = 2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def line_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 4) -> None:
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    if abs(x2 - x1) >= abs(y2 - y1):
        d = 1 if x2 >= x1 else -1
        pts = [(x2, y2), (x2 - d * 18, y2 - 9), (x2 - d * 18, y2 + 9)]
    else:
        d = 1 if y2 >= y1 else -1
        pts = [(x2, y2), (x2 - 9, y2 - d * 18), (x2 + 9, y2 - d * 18)]
    draw.polygon(pts, fill=color)


def polyline_arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, width: int = 4) -> None:
    for a, b in zip(points, points[1:]):
        draw.line((a, b), fill=color, width=width)
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    if abs(x2 - x1) >= abs(y2 - y1):
        d = 1 if x2 >= x1 else -1
        pts = [(x2, y2), (x2 - d * 18, y2 - 9), (x2 - d * 18, y2 + 9)]
    else:
        d = 1 if y2 >= y1 else -1
        pts = [(x2, y2), (x2 - 9, y2 - d * 18), (x2 + 9, y2 - d * 18)]
    draw.polygon(pts, fill=color)


def label(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: str, align: str = "left") -> None:
    lines = text.split("\n")
    bbox = draw.multiline_textbbox((0, 0), text, font=F_LABEL, spacing=5)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 9, 6
    bx = x if align == "left" else x - tw - pad_x * 2
    rect(draw, (bx, y, bx + tw + pad_x * 2, y + th + pad_y * 2), BG, "#E2E8F0", radius=8, width=1)
    draw.multiline_text((bx + pad_x, y + pad_y), text, font=F_LABEL, fill=color, spacing=5)


def draw_node(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, body: str, fill: str, color: str) -> None:
    rect(draw, box, fill, color, radius=26, width=3)
    x1, y1, x2, y2 = box
    center_text(draw, (x1 + 15, y1 + 16, x2 - 15, y1 + 70), title, F_NODE, color)
    center_text(draw, (x1 + 28, y1 + 83, x2 - 28, y2 - 18), body, F_BODY, INK)


def draw_png() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 42), "故障演化采样相位转换图", font=F_TITLE, fill=INK)
    draw.text(
        (70, 92),
        "按优先级依据设备紧迫度 U、字段优先级 F、执行压力 E 和综合控制分 C 选择采样相位。",
        font=F_SUB,
        fill=MUTED,
    )

    input_box = (80, 290, 420, 440)
    focus_box = (700, 185, 1085, 335)
    recovery_box = (700, 475, 1085, 625)
    cruise_box = (150, 725, 535, 875)
    degraded_box = (1385, 725, 1770, 875)

    rect(draw, input_box, FILL_INPUT, STROKE, radius=22)
    center_text(draw, (100, 305, 400, 350), "每轮输入", F_BODY, TEAL)
    center_text(draw, (105, 358, 395, 428), "快线指标 + 慢字段刷新轮数\noutbox / ring / uploader 反馈", F_SMALL, INK)

    draw_node(draw, focus_box, "聚焦采样 FOCUS", "设备异常或风险很高\n最小间隔采样，通常全量补采", FILL_FOCUS, RED)
    draw_node(draw, recovery_box, "恢复观测 RECOVERY", "风险回落但仍需观察\n中高频采样，按需补采慢字段", FILL_RECOVERY, BLUE)
    draw_node(draw, cruise_box, "巡航巡检 CRUISE", "状态稳定、压力正常\n低频快线保活，周期性补采", FILL_CRUISE, GREEN)
    draw_node(draw, degraded_box, "边端降级 DEGRADED", "上传或缓存压力过高\n保留关键快字段，优先本地可靠保存", FILL_DEGRADED, AMBER)

    # Input to focus, clean and unobstructed.
    line_arrow(draw, (420, 365), (700, 260), TEAL)
    label(draw, 475, 285, "计算 U / F / E / C\n若满足聚焦条件", TEAL)

    # Focus hold and focus -> recovery.
    hold_focus = (1135, 198, 1325, 318)
    rect(draw, hold_focus, FILL_NOTE, "#FCA5A5", radius=14)
    center_text(draw, hold_focus, "FOCUS 保持\nfocus_hold > 0\n继续聚焦 1 轮", F_SMALL, RED)
    line_arrow(draw, (1135, 258), (1085, 258), RED, width=3)
    line_arrow(draw, (892, 335), (892, 475), BLUE)
    label(draw, 925, 378, "聚焦触发消失后\n进入恢复观测", BLUE)

    # Recovery hold.
    hold_recovery = (1135, 490, 1325, 610)
    rect(draw, hold_recovery, FILL_NOTE, "#93C5FD", radius=14)
    center_text(draw, hold_recovery, "RECOVERY 保持\nrecovery_hold > 0\n继续观察 1 轮", F_SMALL, BLUE)
    line_arrow(draw, (1135, 550), (1085, 550), BLUE, width=3)

    # Cruise <-> Recovery: separated routes.
    polyline_arrow(draw, [(535, 780), (610, 780), (610, 535), (700, 535)], BLUE)
    label(draw, 460, 648, "U≥30 或 F≥40 或 C≥28", BLUE)
    polyline_arrow(draw, [(700, 600), (650, 600), (650, 845), (535, 845)], GREEN)
    label(draw, 520, 900, "风险低且保持期结束", GREEN)

    # Degraded <-> Recovery: separated and clean.
    polyline_arrow(draw, [(1085, 585), (1225, 585), (1225, 780), (1385, 780)], AMBER)
    label(draw, 1170, 665, "E≥78 且 U<58", AMBER)
    polyline_arrow(draw, [(1385, 845), (1280, 845), (1280, 615), (1085, 615)], BLUE)
    label(draw, 1160, 878, "压力缓解但仍需观察", BLUE)

    # Any phase to focus rule as a note instead of messy cross arrows.
    # rect(draw, (1280, 185, 1830, 335), FILL_NOTE, "#FCA5A5", radius=18)
    # center_text(
    #     draw,
    #     (1300, 200, 1810, 320),
    #     "最高优先级转入 FOCUS\n设备异常 / U≥58 / C≥50 / U≥44且F≥52\n无论当前在哪个相位，下一轮都优先聚焦",
    #     F_SMALL,
    #     RED,
    # )

    # Priority panel at bottom, away from arrows.
    rect(draw, (80, 950, 1860, 1060), FILL_NOTE, STROKE, radius=18)
    draw.text((105, 972), "相位判定优先级：", font=font(18, True), fill=TEAL)
    priority = (
        "1 FOCUS触发  →  2 FOCUS保持  →  3 DEGRADED(E≥78且U<58)  →  "
        "4 RECOVERY(U≥30或F≥40或C≥28)  →  5 RECOVERY保持  →  6 CRUISE"
    )
    draw.text((105, 1012), priority, font=F_LABEL, fill=INK)
    draw.text((70, 1090), "U=设备紧迫度；F=字段优先级；E=执行压力；C=综合控制分。", font=F_SMALL, fill=MUTED)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT)


def svg_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str, rx: int = 20, width: int = 2) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def svg_center(x: int, y: int, w: int, h: int, text: str, size: int = 18, color: str = INK, weight: str = "400") -> str:
    lines = text.split("\n")
    line_h = size * 1.25
    start = y + h / 2 - (len(lines) - 1) * line_h / 2 + size * 0.35
    return "\n".join(
        f'<text x="{x + w / 2}" y="{start + i * line_h}" text-anchor="middle" font-family="Microsoft YaHei, Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )


def svg_text(x: int, y: int, text: str, size: int = 18, color: str = INK, weight: str = "400") -> str:
    return f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, Arial" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(text)}</text>'


def svg_line(x1: int, y1: int, x2: int, y2: int, color: str, width: int = 4) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" marker-end="url(#{color[1:]})"/>'


def svg_path(points: list[tuple[int, int]], color: str, width: int = 4) -> str:
    d = " ".join(("M" if i == 0 else "L") + f"{x},{y}" for i, (x, y) in enumerate(points))
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" marker-end="url(#{color[1:]})"/>'


def svg_label(x: int, y: int, text: str, color: str, w: int = 250, h: int = 54) -> str:
    return svg_rect(x, y, w, h, BG, "#E2E8F0", 8, 1) + svg_center(x, y, w, h, text, 16, color)


def draw_svg() -> None:
    colors = [TEAL, BLUE, GREEN, AMBER, RED]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
    ]
    for c in colors:
        parts.extend(
            [
                f'<marker id="{c[1:]}" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">',
                f'<path d="M2,2 L10,6 L2,10 Z" fill="{c}"/>',
                "</marker>",
            ]
        )
    parts.extend(
        [
            "</defs>",
            f'<rect width="{W}" height="{H}" fill="{BG}"/>',
            svg_text(70, 75, "故障演化采样相位转换图", 34, INK, "700"),
            svg_text(70, 112, "按优先级依据设备紧迫度 U、字段优先级 F、执行压力 E 和综合控制分 C 选择采样相位。", 20, MUTED),
            svg_rect(80, 290, 340, 150, FILL_INPUT, STROKE, 22),
            svg_center(100, 305, 300, 45, "每轮输入", 19, TEAL, "700"),
            svg_center(105, 358, 290, 70, "快线指标 + 慢字段刷新轮数\noutbox / ring / uploader 反馈", 16, INK),
            svg_rect(700, 185, 385, 150, FILL_FOCUS, RED, 26, 3),
            svg_center(715, 201, 355, 54, "聚焦采样 FOCUS", 27, RED, "700"),
            svg_center(728, 268, 329, 48, "设备异常或风险很高\n最小间隔采样，通常全量补采", 18, INK),
            svg_rect(700, 475, 385, 150, FILL_RECOVERY, BLUE, 26, 3),
            svg_center(715, 491, 355, 54, "恢复观测 RECOVERY", 27, BLUE, "700"),
            svg_center(728, 558, 329, 48, "风险回落但仍需观察\n中高频采样，按需补采慢字段", 18, INK),
            svg_rect(150, 725, 385, 150, FILL_CRUISE, GREEN, 26, 3),
            svg_center(165, 741, 355, 54, "巡航巡检 CRUISE", 27, GREEN, "700"),
            svg_center(178, 808, 329, 48, "状态稳定、压力正常\n低频快线保活，周期性补采", 18, INK),
            svg_rect(1385, 725, 385, 150, FILL_DEGRADED, AMBER, 26, 3),
            svg_center(1400, 741, 355, 54, "边端降级 DEGRADED", 27, AMBER, "700"),
            svg_center(1413, 808, 329, 48, "上传或缓存压力过高\n保留关键快字段，优先本地可靠保存", 18, INK),
            svg_line(420, 365, 700, 260, TEAL),
            svg_label(475, 285, "计算 U / F / E / C\n若满足聚焦条件", TEAL),
            svg_line(892, 335, 892, 475, BLUE),
            svg_label(925, 378, "聚焦触发消失后\n进入恢复观测", BLUE),
            svg_path([(535, 780), (610, 780), (610, 535), (700, 535)], BLUE),
            svg_label(460, 648, "U≥30 或 F≥40 或 C≥28", BLUE, 260, 44),
            svg_path([(700, 600), (650, 600), (650, 845), (535, 845)], GREEN),
            svg_label(520, 900, "风险低且保持期结束", GREEN, 230, 44),
            svg_path([(1085, 585), (1225, 585), (1225, 780), (1385, 780)], AMBER),
            svg_label(1170, 665, "E≥78 且 U<58", AMBER, 190, 44),
            svg_path([(1385, 845), (1280, 845), (1280, 615), (1085, 615)], BLUE),
            svg_label(1160, 878, "压力缓解但仍需观察", BLUE, 230, 44),
            svg_rect(1135, 198, 190, 120, FILL_NOTE, "#FCA5A5", 14),
            svg_center(1135, 198, 190, 120, "FOCUS 保持\nfocus_hold > 0\n继续聚焦 1 轮", 16, RED),
            svg_line(1135, 258, 1085, 258, RED, 3),
            svg_rect(1135, 490, 190, 120, FILL_NOTE, "#93C5FD", 14),
            svg_center(1135, 490, 190, 120, "RECOVERY 保持\nrecovery_hold > 0\n继续观察 1 轮", 16, BLUE),
            svg_line(1135, 550, 1085, 550, BLUE, 3),
            svg_rect(1280, 185, 550, 150, FILL_NOTE, "#FCA5A5", 18),
            svg_center(1300, 200, 510, 120, "最高优先级转入 FOCUS\n设备异常 / U≥58 / C≥50 / U≥44且F≥52\n无论当前在哪个相位，下一轮都优先聚焦", 16, RED),
            svg_rect(80, 950, 1780, 110, FILL_NOTE, STROKE, 18),
            svg_text(105, 995, "相位判定优先级：", 18, TEAL, "700"),
            svg_text(105, 1032, "1 FOCUS触发  →  2 FOCUS保持  →  3 DEGRADED(E≥78且U<58)  →  4 RECOVERY(U≥30或F≥40或C≥28)  →  5 RECOVERY保持  →  6 CRUISE", 17, INK),
            svg_text(70, 1095, "U=设备紧迫度；F=字段优先级；E=执行压力；C=综合控制分。", 16, MUTED),
            "</svg>",
        ]
    )
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    draw_png()
    draw_svg()
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {SVG_OUT}")


if __name__ == "__main__":
    main()
