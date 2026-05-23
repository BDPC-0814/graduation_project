from __future__ import annotations

from pathlib import Path
from textwrap import wrap
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
PNG_OUT = FIG_DIR / "研究任务2_故障演化采样理论模型.png"
SVG_OUT = FIG_DIR / "研究任务2_故障演化采样理论模型.svg"

W, H = 2200, 1120

BG = "#FFFFFF"
INK = "#1F2937"
MUTED = "#64748B"
LINE = "#CBD5E1"
TEAL = "#0F766E"
BLUE = "#2563EB"
AMBER = "#B45309"
GREEN = "#15803D"
RED = "#B91C1C"
PANEL = "#F8FAFC"
SOFT_TEAL = "#DDF4EF"
SOFT_BLUE = "#E8F0FF"
SOFT_AMBER = "#FFF1D6"
SOFT_RED = "#FEE2E2"


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


F_TITLE = font(42, True)
F_SUB = font(24)
F_HEAD = font(28, True)
F_BODY = font(22)
F_FORMULA = font(20)
F_SMALL = font(19)
F_TAG = font(20, True)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=LINE, radius=22, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def center(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill=INK, spacing=6):
    lines = text.split("\n")
    sizes = [draw.textbbox((0, 0), line, font=fnt) for line in lines]
    heights = [b[3] - b[1] for b in sizes]
    widths = [b[2] - b[0] for b in sizes]
    total_h = sum(heights) + (len(lines) - 1) * spacing
    x1, y1, x2, y2 = box
    y = y1 + (y2 - y1 - total_h) / 2
    for line, tw, th in zip(lines, widths, heights):
        draw.text((x1 + (x2 - x1 - tw) / 2, y), line, font=fnt, fill=fill)
        y += th + spacing


def paragraph(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill=INK, width=28, spacing=8):
    x, y = xy
    for raw in text.split("\n"):
        lines = wrap(raw, width=width, replace_whitespace=False) if raw else [""]
        for line in lines:
            draw.text((x, y), line, font=fnt, fill=fill)
            y += fnt.size + spacing
    return y


def formula(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color=INK):
    draw.text((x, y), text, font=F_FORMULA, fill=color)
    return y + 42


def draw_curve(draw: ImageDraw.ImageDraw, box):
    x1, y1, x2, y2 = box
    rounded(draw, box, "#FFFFFF", "#DBEAFE", radius=16, width=2)
    pad_l, pad_r, pad_t, pad_b = 70, 35, 42, 70
    ax0, ay0 = x1 + pad_l, y2 - pad_b
    ax1, ay1 = x2 - pad_r, y1 + pad_t
    draw.line((ax0, ay0, ax1, ay0), fill="#94A3B8", width=2)
    draw.line((ax0, ay0, ax0, ay1), fill="#94A3B8", width=2)
    for i in range(1, 4):
        x = ax0 + (ax1 - ax0) * i / 4
        draw.line((x, ay0, x, ay1), fill="#E2E8F0", width=1)
        y = ay0 - (ay0 - ay1) * i / 4
        draw.line((ax0, y, ax1, y), fill="#E2E8F0", width=1)

    points = []
    for c in range(0, 101, 5):
        # A presentation curve for the implemented piecewise rule: higher control score means shorter interval.
        interval = max(0.5, 8.0 - 7.5 * (c / 100.0) ** 0.82)
        px = ax0 + (ax1 - ax0) * c / 100
        py = ay0 - (ay0 - ay1) * (interval - 0.5) / 7.5
        points.append((px, py))
    draw.line(points, fill=BLUE, width=5)
    for px, py in points[::5]:
        draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=BLUE)

    draw.text((ax0 - 12, ay0 + 24), "0", font=F_SMALL, fill=MUTED)
    draw.text((ax1 - 42, ay0 + 24), "100", font=F_SMALL, fill=MUTED)
    draw.text((ax0 + 185, ay0 + 24), "综合控制分 C(t)", font=F_SMALL, fill=MUTED)
    draw.text((x1 + 18, ay1 - 10), "Δt", font=F_SMALL, fill=MUTED)
    draw.text((ax0 + 12, ay1 + 12), "低频/大间隔", font=F_SMALL, fill=MUTED)
    draw.text((ax0 + 12, ay0 - 34), "高频/小间隔", font=F_SMALL, fill=BLUE)
    draw.text((ax0 + 8, y1 + 10), "风险升高时 Δt 缩短", font=F_SMALL, fill=BLUE)


def draw_png() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((70, 42), "面向故障演化过程的自适应采样理论模型", font=F_TITLE, fill=INK)
    draw.text(
        (70, 94),
        "用连续控制量替代固定频率：先量化设备风险与边端压力，再动态决定采样间隔、字段集合和缓存策略。",
        font=F_SUB,
        fill=MUTED,
    )

    tags = [
        ("针对问题", "指标缺失、故障窗口短、固定采样冗余高、边端链路不稳定", SOFT_RED, RED),
        ("提出方法", "U/F/E/C 四类控制量 + 分段采样函数 + 快慢字段分层", SOFT_BLUE, BLUE),
        ("形成效果", "关键窗口升频、稳定阶段降冗余、链路承压时可靠保存", SOFT_TEAL, TEAL),
    ]
    x = 70
    for title, body, fill, color in tags:
        rounded(draw, (x, 145, x + 650, 220), fill, color, radius=18, width=2)
        draw.text((x + 24, 169), title, font=F_TAG, fill=color)
        draw.text((x + 138, 169), body, font=F_SMALL, fill=INK)
        x += 700

    panels = [
        (70, 255, 705, 790, "1  风险量化", TEAL),
        (780, 255, 1415, 790, "2  采样决策", BLUE),
        (1490, 255, 2125, 790, "3  字段与链路控制", AMBER),
    ]
    for x1, y1, x2, y2, title, color in panels:
        rounded(draw, (x1, y1, x2, y2), PANEL, LINE, radius=24, width=2)
        draw.text((x1 + 28, y1 + 24), title, font=F_HEAD, fill=color)

    # Panel 1: formulas close to the implementation.
    y = 330
    draw.text((100, y), "归一化采集指标：", font=F_BODY, fill=INK)
    y += 42
    y = formula(draw, 100, y, "x_hat_k(t)=clip((x_k(t)-L_k)/(H_k-L_k),0,1)", TEAL)
    draw.text((100, y), "x_k 缺失时不伪造数值，该风险项记 0；异常状态单独加权。", font=F_SMALL, fill=MUTED)
    y += 48
    y = formula(draw, 100, y, "U(t)=clip(Σa_k x_hat_k +18I_throttle+24I_abn,0,100)")
    y = formula(draw, 100, y, "F(t)=clip(S_stale+S_vol+S_drift+S_temp+S_power+16I_event,0,100)")
    y = formula(draw, 100, y, "E(t)=clip(28Q_pending+35Q_dead+25Q_ring+10I_offline,0,100)")
    y = formula(draw, 100, y, "C(t)=clip(0.52U(t)+0.36F(t)-0.30E(t),0,100)", RED)

    # Panel 2: decision function plus curve.
    y = 330
    y = formula(draw, 810, y, "p(t)=R(U,F,E,C)")
    y = formula(draw, 810, y, "Δt(t)=G(p,U,F,E,C)")
    draw.text((810, y + 2), "其中 R 是阈值判定函数，G 是分段采样间隔函数。", font=F_SMALL, fill=MUTED)
    draw_curve(draw, (820, 455, 1375, 745))
    draw.text((835, 760), "FOCUS：Δt=t_min；CRUISE：低风险时 Δt→t_max", font=F_SMALL, fill=BLUE)

    # Panel 3: field and transport policy.
    y = 330
    y = formula(draw, 1520, y, "s_j(t)=1[F_j(t) >= θ_p]")
    draw.text((1520, y), "字段优先级超过当前阈值时，补采对应慢字段。", font=F_SMALL, fill=MUTED)
    y += 54
    y = formula(draw, 1520, y, "B(t)=1[E(t)>=78 and U(t)<58]", AMBER)
    draw.text((1520, y), "边端压力高且设备风险未达到聚焦阈值时，优先本地缓存。", font=F_SMALL, fill=MUTED)
    y += 54
    y = formula(draw, 1520, y, "policy(t)={direct, buffered, local, degraded}", AMBER)
    draw.text((1520, y), "根据 outbox、ring、uploader 状态选择上传或降级保存。", font=F_SMALL, fill=MUTED)
    rounded(draw, (1520, 650, 2090, 745), "#FFFFFF", "#FCD34D", radius=16, width=2)
    center(draw, (1530, 660, 2080, 735), "边端可靠链路：RingBuffer 吸峰 + SQLite WAL 持久化 + 异步重试", F_SMALL, AMBER)

    # Outcome row.
    rounded(draw, (70, 840, 2125, 1035), "#FFFFFF", LINE, radius=24, width=2)
    draw.text((105, 870), "理论落点", font=F_HEAD, fill=TEAL)
    outcomes = [
        ("关键窗口高密度捕获", "U 或 C 快速升高时压缩 Δt，并触发慢字段补采。", BLUE),
        ("稳定阶段低冗余采样", "U、F 长期偏低时回到巡航间隔，减少重复快照。", GREEN),
        ("边端压力下可靠保存", "E 升高时降低非关键采集和上传压力，保证关键数据不丢。", AMBER),
    ]
    x = 105
    for title, body, color in outcomes:
        rounded(draw, (x, 925, x + 615, 1005), "#F8FAFC", color, radius=18, width=2)
        draw.text((x + 24, 947), title, font=F_TAG, fill=color)
        draw.text((x + 24, 977), body, font=F_SMALL, fill=INK)
        x += 670

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT)


def svg_text(x: int, y: int, text: str, size: int, color: str = INK, weight: str = "400") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, Arial" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{escape(text)}</text>'
    )


def svg_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str = LINE, rx: int = 18, width: int = 2) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def draw_svg() -> None:
    # A compact vector companion for PPT export; the PNG is the primary polished asset.
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        svg_text(70, 82, "面向故障演化过程的自适应采样理论模型", 42, INK, "700"),
        svg_text(70, 126, "用连续控制量替代固定频率：先量化设备风险与边端压力，再动态决定采样间隔、字段集合和缓存策略。", 24, MUTED),
    ]
    for x, title, body, fill, color in [
        (70, "针对问题", "指标缺失、故障窗口短、固定采样冗余高、边端链路不稳定", SOFT_RED, RED),
        (770, "提出方法", "U/F/E/C 四类控制量 + 分段采样函数 + 快慢字段分层", SOFT_BLUE, BLUE),
        (1470, "形成效果", "关键窗口升频、稳定阶段降冗余、链路承压时可靠保存", SOFT_TEAL, TEAL),
    ]:
        parts.append(svg_rect(x, 145, 650, 75, fill, color))
        parts.append(svg_text(x + 24, 193, title, 20, color, "700"))
        parts.append(svg_text(x + 138, 193, body, 19, INK))

    for x, title, color in [
        (70, "1  风险量化", TEAL),
        (780, "2  采样决策", BLUE),
        (1490, "3  字段与链路控制", AMBER),
    ]:
        parts.append(svg_rect(x, 255, 635, 535, PANEL, LINE, 24))
        parts.append(svg_text(x + 28, 312, title, 28, color, "700"))

    formulas_left = [
        (100, 380, "x_hat_k(t)=clip((x_k(t)-L_k)/(H_k-L_k),0,1)", TEAL),
        (100, 456, "U(t)=clip(Σa_k x_hat_k +18I_throttle+24I_abn,0,100)", INK),
        (100, 502, "F(t)=clip(S_stale+S_vol+S_drift+S_temp+S_power+16I_event,0,100)", INK),
        (100, 548, "E(t)=clip(28Q_pending+35Q_dead+25Q_ring+10I_offline,0,100)", INK),
        (100, 594, "C(t)=clip(0.52U(t)+0.36F(t)-0.30E(t),0,100)", RED),
    ]
    parts.append(svg_text(100, 348, "归一化采集指标：", 22, INK))
    parts.append(svg_text(100, 424, "x_k 缺失时不伪造数值，该风险项记 0；异常状态单独加权。", 19, MUTED))
    for x, y, text, color in formulas_left:
        parts.append(svg_text(x, y, text, 24, color))

    parts.extend(
        [
            svg_text(810, 380, "p(t)=R(U,F,E,C)", 24, INK),
            svg_text(810, 426, "Δt(t)=G(p,U,F,E,C)", 24, INK),
            svg_text(810, 468, "其中 R 是阈值判定函数，G 是分段采样间隔函数。", 19, MUTED),
            svg_rect(820, 455, 555, 290, "#FFFFFF", "#DBEAFE", 16),
            '<line x1="890" y1="675" x2="1340" y2="675" stroke="#94A3B8" stroke-width="2"/>',
            '<line x1="890" y1="675" x2="890" y2="497" stroke="#94A3B8" stroke-width="2"/>',
            '<path d="M890,500 C990,525 1070,575 1165,615 C1235,648 1295,669 1340,674" fill="none" stroke="#2563EB" stroke-width="5"/>',
            svg_text(1005, 724, "综合控制分 C(t)", 19, MUTED),
            svg_text(910, 517, "低频/大间隔", 19, MUTED),
            svg_text(910, 654, "高频/小间隔", 19, BLUE),
            svg_text(835, 783, "FOCUS：Δt=t_min；CRUISE：低风险时 Δt→t_max", 19, BLUE),
            svg_text(1520, 380, "s_j(t)=1[F_j(t) >= θ_p]", 24, INK),
            svg_text(1520, 424, "字段优先级超过当前阈值时，补采对应慢字段。", 19, MUTED),
            svg_text(1520, 502, "B(t)=1[E(t)>=78 and U(t)<58]", 24, AMBER),
            svg_text(1520, 546, "边端压力高且设备风险未达到聚焦阈值时，优先本地缓存。", 19, MUTED),
            svg_text(1520, 624, "policy(t)={direct, buffered, local, degraded}", 24, AMBER),
            svg_text(1520, 668, "根据 outbox、ring、uploader 状态选择上传或降级保存。", 19, MUTED),
            svg_rect(70, 840, 2055, 195, "#FFFFFF", LINE, 24),
            svg_text(105, 900, "理论落点", 28, TEAL, "700"),
        ]
    )
    for x, title, body, color in [
        (105, "关键窗口高密度捕获", "U 或 C 快速升高时压缩 Δt，并触发慢字段补采。", BLUE),
        (775, "稳定阶段低冗余采样", "U、F 长期偏低时回到巡航间隔，减少重复快照。", GREEN),
        (1445, "边端压力下可靠保存", "E 升高时降低非关键采集和上传压力，保证关键数据不丢。", AMBER),
    ]:
        parts.append(svg_rect(x, 925, 615, 80, "#F8FAFC", color, 18))
        parts.append(svg_text(x + 24, 963, title, 20, color, "700"))
        parts.append(svg_text(x + 24, 994, body, 19, INK))

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
