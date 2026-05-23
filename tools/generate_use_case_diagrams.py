# -*- coding: utf-8 -*-
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BLACK = "#111111"
WHITE = "#ffffff"
GRAY = "#f8f8f8"


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


F_TITLE = font(21, True)
F_CASE = font(18)
F_ACTOR = font(18)
F_SMALL = font(16)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> List[str]:
    lines: List[str] = []
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


def center_text(
    draw: ImageDraw.ImageDraw,
    box: Tuple[float, float, float, float],
    text: str,
    fnt,
    fill: str = BLACK,
    max_width: Optional[int] = None,
    line_gap: int = 2,
):
    x1, y1, x2, y2 = box
    max_width = max_width or int(x2 - x1 - 18)
    lines = wrap_text(draw, text, fnt, max_width)
    heights = [text_size(draw, line, fnt)[1] for line in lines]
    total_h = sum(heights) + line_gap * max(len(lines) - 1, 0)
    y = y1 + (y2 - y1 - total_h) / 2
    for line, h in zip(lines, heights):
        w, _ = text_size(draw, line, fnt)
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + line_gap


def ellipse_box(cx: float, cy: float, w: float, h: float) -> Tuple[float, float, float, float]:
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def draw_use_case(draw: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, label: str):
    box = ellipse_box(cx, cy, w, h)
    draw.ellipse(box, fill=WHITE, outline=BLACK, width=2)
    center_text(draw, box, label, F_CASE)


def draw_actor(draw: ImageDraw.ImageDraw, cx: float, cy: float, label: str):
    # cy is the head center.
    draw.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=WHITE, outline=BLACK, width=2)
    draw.line((cx, cy + 12, cx, cy + 68), fill=BLACK, width=2)
    draw.line((cx - 33, cy + 35, cx + 33, cy + 35), fill=BLACK, width=2)
    draw.line((cx, cy + 68, cx - 28, cy + 112), fill=BLACK, width=2)
    draw.line((cx, cy + 68, cx + 28, cy + 112), fill=BLACK, width=2)
    center_text(draw, (cx - 70, cy + 118, cx + 70, cy + 170), label, F_ACTOR)


def line(draw: ImageDraw.ImageDraw, start: Tuple[float, float], end: Tuple[float, float]):
    draw.line((*start, *end), fill=BLACK, width=2)


def draw_boundary(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], title: str):
    draw.rectangle(box, fill=WHITE, outline=BLACK, width=2)
    x1, y1, x2, _ = box
    center_text(draw, (x1, y1 + 8, x2, y1 + 40), title, F_TITLE)


def svg_header(w: int, h: int) -> List[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<style>text{font-family:"Microsoft YaHei","SimHei",Arial,sans-serif;}</style>',
        f'<rect width="{w}" height="{h}" fill="{WHITE}"/>',
    ]


def svg_center_text(x: float, y: float, text: str, size: int = 18, weight: int = 400, max_chars: int = 9) -> str:
    lines: List[str] = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        current += ch
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    if not lines:
        lines = [text]
    start = y - (len(lines) - 1) * (size + 3) / 2
    spans = [f'<tspan x="{x}" y="{start + i * (size + 3)}">{line}</tspan>' for i, line in enumerate(lines)]
    return f'<text text-anchor="middle" dominant-baseline="middle" font-size="{size}" font-weight="{weight}" fill="{BLACK}">' + "".join(spans) + "</text>"


def svg_use_case(cx: float, cy: float, w: float, h: float, label: str) -> str:
    return (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{w / 2}" ry="{h / 2}" fill="{WHITE}" stroke="{BLACK}" stroke-width="2"/>'
        + svg_center_text(cx, cy, label, 18, 400, max_chars=8)
    )


def svg_actor(cx: float, cy: float, label: str) -> str:
    return "\n".join(
        [
            f'<circle cx="{cx}" cy="{cy}" r="12" fill="{WHITE}" stroke="{BLACK}" stroke-width="2"/>',
            f'<line x1="{cx}" y1="{cy + 12}" x2="{cx}" y2="{cy + 68}" stroke="{BLACK}" stroke-width="2"/>',
            f'<line x1="{cx - 33}" y1="{cy + 35}" x2="{cx + 33}" y2="{cy + 35}" stroke="{BLACK}" stroke-width="2"/>',
            f'<line x1="{cx}" y1="{cy + 68}" x2="{cx - 28}" y2="{cy + 112}" stroke="{BLACK}" stroke-width="2"/>',
            f'<line x1="{cx}" y1="{cy + 68}" x2="{cx + 28}" y2="{cy + 112}" stroke="{BLACK}" stroke-width="2"/>',
            svg_center_text(cx, cy + 145, label, 18, 400, max_chars=6),
        ]
    )


def svg_line(start: Tuple[float, float], end: Tuple[float, float]) -> str:
    return f'<line x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" stroke="{BLACK}" stroke-width="2"/>'


def save_diagram(
    name: str,
    size: Tuple[int, int],
    boundary: Tuple[int, int, int, int],
    title: str,
    actors: Sequence[Tuple[str, float, float]],
    cases: Sequence[Tuple[str, float, float, float, float]],
    links: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]],
):
    w, h = size
    png_path = OUT_DIR / f"{name}.png"
    svg_path = OUT_DIR / f"{name}.svg"

    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    draw_boundary(draw, boundary, title)
    for start, end in links:
        line(draw, start, end)
    for _, cx, cy, cw, ch in cases:
        draw_use_case(draw, cx, cy, cw, ch, _)
    for label, cx, cy in actors:
        draw_actor(draw, cx, cy, label)
    img.save(png_path)

    parts = svg_header(w, h)
    x1, y1, x2, y2 = boundary
    parts.append(f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" fill="{WHITE}" stroke="{BLACK}" stroke-width="2"/>')
    parts.append(svg_center_text((x1 + x2) / 2, y1 + 25, title, 21, 700, max_chars=18))
    for start, end in links:
        parts.append(svg_line(start, end))
    for label, cx, cy, cw, ch in cases:
        parts.append(svg_use_case(cx, cy, cw, ch, label))
    for label, cx, cy in actors:
        parts.append(svg_actor(cx, cy, label))
    parts.append("</svg>")
    svg_path.write_text("\n".join(parts), encoding="utf-8")


def actor_link(actor: Tuple[float, float], case: Tuple[float, float]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    ax, ay = actor
    return (ax + 34, ay + 35), case


def build_total():
    actors = [
        ("监控\n观察者", 105, 145),
        ("实验\n操作者", 105, 405),
        ("系统\n维护者", 105, 665),
    ]
    cases = [
        ("设备状态监控", 390, 110, 190, 56),
        ("趋势曲线查看", 650, 110, 190, 56),
        ("事件日志查看", 910, 110, 190, 56),
        ("实验评估查看", 1040, 210, 190, 56),
        ("回放轨迹生成", 390, 330, 190, 56),
        ("采样模式选择", 650, 330, 190, 56),
        ("实时采集启动", 910, 330, 190, 56),
        ("回放对照实验", 1040, 430, 190, 56),
        ("任务进度查看", 650, 510, 190, 56),
        ("系统健康检查", 390, 650, 190, 56),
        ("数据接收检查", 650, 650, 190, 56),
        ("数据库写入检查", 910, 650, 190, 56),
        ("缓存重试检查", 1040, 750, 190, 56),
        ("异常告警查看", 650, 770, 190, 56),
    ]
    links = [
        actor_link((105, 145), (300, 110)),
        actor_link((105, 145), (555, 110)),
        actor_link((105, 145), (815, 110)),
        actor_link((105, 145), (945, 210)),
        actor_link((105, 405), (300, 330)),
        actor_link((105, 405), (555, 330)),
        actor_link((105, 405), (815, 330)),
        actor_link((105, 405), (945, 430)),
        actor_link((105, 405), (555, 510)),
        actor_link((105, 665), (300, 650)),
        actor_link((105, 665), (555, 650)),
        actor_link((105, 665), (815, 650)),
        actor_link((105, 665), (945, 750)),
        actor_link((105, 665), (555, 770)),
    ]
    save_diagram(
        "图3_3_系统总体用例图",
        (1200, 900),
        (230, 45, 1160, 850),
        "自适应变频数据采集系统",
        actors,
        cases,
        links,
    )


def build_role_diagram(name: str, title: str, actor_label: str, labels: Sequence[str]):
    # The role-specific diagrams share one actor and a two-column use-case layout.
    coords = [
        (360, 110),
        (610, 110),
        (360, 205),
        (610, 205),
        (360, 300),
        (610, 300),
        (360, 395),
        (610, 395),
        (485, 500),
    ]
    cases = [(label, x, y, 190, 56) for label, (x, y) in zip(labels, coords)]
    actors = [(actor_label, 95, 250)]
    actor_point = (95, 250)
    links = [actor_link(actor_point, (x - 95, y)) for _, x, y, _, _ in cases]
    save_diagram(name, (820, 620), (220, 45, 775, 560), title, actors, cases, links)


def build_all():
    build_total()
    build_role_diagram(
        "图3_4_监控观察者角色用例图",
        "监控观察者用例",
        "监控\n观察者",
        [
            "查看设备总数",
            "查看在线设备数",
            "查看采样间隔",
            "查看演化分数",
            "查看温度功耗",
            "查看趋势曲线",
            "查看最近事件",
            "查看运行日志",
            "查看评估结果",
        ],
    )
    build_role_diagram(
        "图3_5_实验操作者角色用例图",
        "实验操作者用例",
        "实验\n操作者",
        [
            "生成回放轨迹",
            "选择采样模式",
            "启动实时采集",
            "执行回放对照",
            "查看任务进度",
            "查看运行日志",
            "查看结果文件",
        ],
    )
    build_role_diagram(
        "图3_6_系统维护者角色用例图",
        "系统维护者用例",
        "系统\n维护者",
        [
            "检查系统健康",
            "检查任务状态",
            "检查数据接收",
            "检查数据库写入",
            "检查缓存积压",
            "检查失败重试",
            "查看异常日志",
            "查看告警信息",
        ],
    )


if __name__ == "__main__":
    build_all()
    for path in sorted(OUT_DIR.glob("图3_*用例图.*")):
        print(path)
