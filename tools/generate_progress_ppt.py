from __future__ import annotations

import csv
import html
import io
import math
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "工作进展汇报_故障演化采样与YS-EC588成果.pptx"

EMU_PER_INCH = 914400
SLIDE_W = 12192000
SLIDE_H = 6858000

BG = "F7F9FB"
INK = "1F2937"
MUTED = "64748B"
LINE = "CBD5E1"
TEAL = "0F766E"
BLUE = "2563EB"
AMBER = "B45309"
GREEN = "15803D"
RED = "B91C1C"
WHITE = "FFFFFF"
SOFT_TEAL = "DDF4EF"
SOFT_BLUE = "E8F0FF"
SOFT_AMBER = "FFF1D6"
SOFT_RED = "FEE2E2"
SOFT_GRAY = "EEF2F7"


def emu(inch: float) -> int:
    return int(round(inch * EMU_PER_INCH))


def xesc(value: object) -> str:
    return html.escape(str(value), quote=True)


def pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def font(size: int = 24) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
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


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def make_npu_chart() -> bytes:
    path = ROOT / "experiments" / "npu_capture" / "real_npu_raw_metrics.csv"
    rows = load_csv(path)
    times = [parse_float(row.get("time")) or 0.0 for row in rows]
    temps = [parse_float(row.get("chip_temp_c")) for row in rows]
    utils = [parse_float(row.get("utilization")) for row in rows]
    points = [(t, temp, util) for t, temp, util in zip(times, temps, utils) if temp is not None and util is not None]
    if not points:
        points = [(0, 38.0, 0.0), (180, 43.0, 1.0)]

    width, height = 1500, 820
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    f_title = font(40)
    f_axis = font(24)
    f_small = font(21)

    margin_l, margin_r, margin_t, margin_b = 120, 70, 70, 180
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=28, fill="#FFFFFF", outline="#CBD5E1", width=2)
    x0, y0 = margin_l, margin_t + plot_h
    x1, y1 = margin_l + plot_w, margin_t
    draw.line((x0, y0, x1, y0), fill="#94A3B8", width=2)
    draw.line((x0, y0, x0, y1), fill="#94A3B8", width=2)

    t_min, t_max = min(p[0] for p in points), max(p[0] for p in points)
    temp_min = math.floor(min(p[1] for p in points)) - 1
    temp_max = math.ceil(max(p[1] for p in points)) + 1
    util_max = max(max(p[2] for p in points), 1.0)

    def sx(t: float) -> float:
        return x0 + (t - t_min) / max(t_max - t_min, 1e-9) * plot_w

    def sy_temp(temp: float) -> float:
        return y0 - (temp - temp_min) / max(temp_max - temp_min, 1e-9) * plot_h

    def sy_util(util: float) -> float:
        return y0 - (util / util_max) * (plot_h * 0.82)

    for i in range(5):
        y = y0 - i * plot_h / 4
        draw.line((x0, y, x1, y), fill="#E2E8F0", width=1)
        label = f"{temp_min + i * (temp_max - temp_min) / 4:.1f}°C"
        draw.text((42, y - 14), label, fill="#64748B", font=f_axis)

    for i in range(5):
        x = x0 + i * plot_w / 4
        draw.line((x, y0, x, y0 + 8), fill="#94A3B8", width=2)
        label = f"{t_min + i * (t_max - t_min) / 4:.0f}s"
        draw.text((x - 24, y0 + 20), label, fill="#64748B", font=f_axis)

    util_poly = [(sx(t), sy_util(util)) for t, _, util in points]
    temp_poly = [(sx(t), sy_temp(temp)) for t, temp, _ in points]
    if len(util_poly) > 1:
        draw.line(util_poly, fill="#2563EB", width=4)
    if len(temp_poly) > 1:
        draw.line(temp_poly, fill="#0F766E", width=5)

    for x, y in temp_poly[:: max(1, len(temp_poly) // 30)]:
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#0F766E")

    legend_y = height - 84
    draw.rounded_rectangle((60, legend_y - 10, 400, legend_y + 46), radius=10, fill="#DDF4EF")
    draw.line((85, legend_y + 18, 145, legend_y + 18), fill="#0F766E", width=5)
    draw.text((160, legend_y), "芯片温度 chip_temp_c", fill="#1F2937", font=f_small)
    draw.rounded_rectangle((430, legend_y - 10, 780, legend_y + 46), radius=10, fill="#E8F0FF")
    draw.line((455, legend_y + 18, 515, legend_y + 18), fill="#2563EB", width=4)
    draw.text((530, legend_y), "NPU 利用率 utilization", fill="#1F2937", font=f_small)
    draw.text((1025, legend_y), f"温度范围：{temp_min + 1:.3g}-{temp_max - 1:.3g}°C", fill="#64748B", font=f_small)

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def make_eval_chart() -> bytes:
    fixed = {
        "冗余率": 29.82,
        "延迟P50": 2.079,
        "延迟P95": 3.4883,
    }
    evolution = {
        "冗余率": 20.00,
        "延迟P50": 1.109,
        "延迟P95": 2.6157,
    }

    width, height = 1500, 820
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    f_title = font(40)
    f_axis = font(24)
    f_small = font(21)
    f_num = font(23)

    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=28, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.text((60, 48), "Fixed vs Evolution 阶段性评估对比", fill="#1F2937", font=f_title)
    draw.text((62, 95), "同一回放轨迹与 ground-truth 事件口径下的指标对比", fill="#64748B", font=f_small)

    x0, y0 = 130, 650
    plot_w, plot_h = 1180, 430
    draw.line((x0, y0, x0 + plot_w, y0), fill="#94A3B8", width=2)
    for i in range(5):
        y = y0 - i * plot_h / 4
        draw.line((x0, y, x0 + plot_w, y), fill="#E2E8F0", width=1)

    categories = list(fixed.keys())
    group_w = plot_w / len(categories)
    bar_w = 86
    for idx, cat in enumerate(categories):
        cx = x0 + group_w * idx + group_w / 2
        max_v = max(fixed[cat], evolution[cat])
        scale = plot_h / max_v
        f_h = fixed[cat] * scale
        e_h = evolution[cat] * scale
        draw.rounded_rectangle((cx - 100, y0 - f_h, cx - 100 + bar_w, y0), radius=10, fill="#94A3B8")
        draw.rounded_rectangle((cx + 10, y0 - e_h, cx + 10 + bar_w, y0), radius=10, fill="#0F766E")
        unit = "%" if "率" in cat else "s"
        draw.text((cx - 120, y0 - f_h - 34), f"{fixed[cat]:.2f}{unit}", fill="#475569", font=f_num)
        draw.text((cx - 4, y0 - e_h - 34), f"{evolution[cat]:.2f}{unit}", fill="#0F766E", font=f_num)
        draw.text((cx - 70, y0 + 28), cat, fill="#1F2937", font=f_axis)

    draw.rounded_rectangle((1230, 160, 1470, 340), radius=18, fill="#DDF4EF", outline="#99D8CC", width=2)
    draw.text((1255, 188), "关键改善", fill="#0F766E", font=font(28))
    draw.text((1255, 236), f"冗余率 -{pct_change(29.82, 20.0):.1f}%", fill="#1F2937", font=f_small)
    draw.text((1255, 272), f"P50 延迟 -{pct_change(2.079, 1.109):.1f}%", fill="#1F2937", font=f_small)
    draw.text((1255, 308), f"P95 延迟 -{pct_change(3.4883, 2.6157):.1f}%", fill="#1F2937", font=f_small)

    legend_y = height - 90
    draw.rounded_rectangle((60, legend_y - 8, 260, legend_y + 42), radius=10, fill="#F1F5F9")
    draw.rectangle((84, legend_y + 8, 116, legend_y + 30), fill="#94A3B8")
    draw.text((130, legend_y), "固定频率", fill="#1F2937", font=f_small)
    draw.rounded_rectangle((300, legend_y - 8, 560, legend_y + 42), radius=10, fill="#DDF4EF")
    draw.rectangle((324, legend_y + 8, 356, legend_y + 30), fill="#0F766E")
    draw.text((370, legend_y), "故障演化采样", fill="#1F2937", font=f_small)

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


@dataclass
class Media:
    name: str
    data: bytes
    content_type: str = "image/png"


@dataclass
class Deck:
    slides: list["Slide"] = field(default_factory=list)
    media: list[Media] = field(default_factory=list)

    def add_media(self, data: bytes, suffix: str = "png") -> str:
        name = f"image{len(self.media) + 1}.{suffix}"
        self.media.append(Media(name=name, data=data))
        return name

    def add_media_file(self, path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".") or "png"
        content_type = "image/jpeg" if suffix in {"jpg", "jpeg"} else "image/png"
        name = f"image{len(self.media) + 1}.{suffix}"
        self.media.append(Media(name=name, data=path.read_bytes(), content_type=content_type))
        return name


@dataclass
class Slide:
    deck: Deck
    title: str
    section: str = ""
    number: int = 0
    elements: list[str] = field(default_factory=list)
    rels: list[tuple[str, str, str]] = field(default_factory=list)
    _shape_id: int = 1
    _rel_id: int = 1

    def __post_init__(self) -> None:
        self.background()

    def next_id(self) -> int:
        self._shape_id += 1
        return self._shape_id

    def next_rid(self) -> str:
        rid = f"rId{self._rel_id}"
        self._rel_id += 1
        return rid

    def background(self) -> None:
        self.add_rect(0, 0, 13.333, 7.5, fill=BG, line=None)

    def header(self) -> None:
        if self.section:
            self.add_text(
                0.55,
                0.18,
                6.5,
                0.28,
                [{"text": self.section, "size": 10, "bold": True, "color": TEAL}],
                color=TEAL,
            )
        self.add_text(
            0.55,
            0.48,
            10.3,
            0.55,
            [{"text": self.title, "size": 25, "bold": True, "color": INK}],
        )
        self.add_rect(0.55, 1.08, 12.2, 0.015, fill=LINE, line=None)
        self.add_text(
            11.65,
            7.05,
            1.1,
            0.22,
            [{"text": f"{self.number:02d}", "size": 8, "color": MUTED, "align": "r"}],
        )

    def add_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str | None = WHITE,
        line: str | None = LINE,
        radius: bool = False,
    ) -> None:
        sid = self.next_id()
        fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
        line_xml = (
            f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
            if line
            else '<a:ln><a:noFill/></a:ln>'
        )
        geom = "roundRect" if radius else "rect"
        self.elements.append(
            f"""
            <p:sp>
              <p:nvSpPr><p:cNvPr id="{sid}" name="Shape {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
              <p:spPr>
                <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
                <a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>
                {fill_xml}{line_xml}
              </p:spPr>
            </p:sp>
            """
        )

    def add_text(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        paragraphs: list[dict[str, object]],
        *,
        fill: str | None = None,
        line: str | None = None,
        radius: bool = False,
        color: str = INK,
        valign: str = "top",
        margin: float = 0.06,
    ) -> None:
        sid = self.next_id()
        fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
        line_xml = (
            f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
            if line
            else '<a:ln><a:noFill/></a:ln>'
        )
        geom = "roundRect" if radius else "rect"
        anchor = "mid" if valign == "mid" else "t"
        para_xml = "\n".join(self._para_xml(p, color) for p in paragraphs)
        self.elements.append(
            f"""
            <p:sp>
              <p:nvSpPr><p:cNvPr id="{sid}" name="Text {sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
              <p:spPr>
                <a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>
                <a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>
                {fill_xml}{line_xml}
              </p:spPr>
              <p:txBody>
                <a:bodyPr wrap="square" anchor="{anchor}" lIns="{emu(margin)}" rIns="{emu(margin)}" tIns="{emu(margin)}" bIns="{emu(margin)}"/>
                <a:lstStyle/>
                {para_xml}
              </p:txBody>
            </p:sp>
            """
        )

    def _para_xml(self, p: dict[str, object], default_color: str) -> str:
        text = str(p.get("text", ""))
        size = int(p.get("size", 16))
        bold = "1" if bool(p.get("bold", False)) else "0"
        col = str(p.get("color", default_color))
        align = str(p.get("align", "l"))
        bullet = bool(p.get("bullet", False))
        prefix = "• " if bullet else ""
        space_after = int(p.get("after", 250))
        return (
            f'<a:p><a:pPr algn="{align}"><a:spcAft><a:spcPts val="{space_after}"/></a:spcAft></a:pPr>'
            f'<a:r><a:rPr lang="zh-CN" sz="{size * 100}" b="{bold}">'
            f'<a:solidFill><a:srgbClr val="{col}"/></a:solidFill>'
            f'<a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/>'
            f"</a:rPr><a:t>{xesc(prefix + text)}</a:t></a:r></a:p>"
        )

    def add_card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        bullets: Iterable[str],
        *,
        fill: str = WHITE,
        accent: str = TEAL,
        title_size: int = 18,
        bullet_size: int = 12,
    ) -> None:
        self.add_rect(x, y, w, h, fill=fill, line=LINE, radius=True)
        self.add_rect(x, y, 0.08, h, fill=accent, line=None, radius=True)
        paras = [{"text": title, "size": title_size, "bold": True, "color": accent}]
        paras.extend({"text": item, "size": bullet_size, "color": INK, "bullet": True} for item in bullets)
        self.add_text(x + 0.16, y + 0.08, w - 0.26, h - 0.16, paras, margin=0.05)

    def add_image(self, media_name: str, x: float, y: float, w: float, h: float) -> None:
        rid = self.next_rid()
        self.rels.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", f"../media/{media_name}"))
        sid = self.next_id()
        self.elements.append(
            f"""
            <p:pic>
              <p:nvPicPr><p:cNvPr id="{sid}" name="{xesc(media_name)}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
              <p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
              <p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
            </p:pic>
            """
        )

    def add_table(
        self,
        x: float,
        y: float,
        col_ws: list[float],
        row_h: float,
        headers: list[str],
        rows: list[list[str]],
        *,
        font_size: int = 10,
    ) -> None:
        xs = [x]
        for cw in col_ws[:-1]:
            xs.append(xs[-1] + cw)
        for ci, header in enumerate(headers):
            self.add_text(xs[ci], y, col_ws[ci], row_h, [{"text": header, "size": font_size, "bold": True, "color": WHITE, "align": "c"}], fill=TEAL, line=WHITE, valign="mid", margin=0.03)
        for ri, row in enumerate(rows):
            yy = y + row_h * (ri + 1)
            fill = WHITE if ri % 2 == 0 else "F8FAFC"
            for ci, value in enumerate(row):
                self.add_text(xs[ci], yy, col_ws[ci], row_h, [{"text": value, "size": font_size, "color": INK}], fill=fill, line=WHITE, valign="mid", margin=0.04)

    def xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {"".join(self.elements)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""

    def rels_xml(self) -> str:
        rels = [("rIdLayout", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml")]
        rels.extend(self.rels)
        body = "\n".join(
            f'<Relationship Id="{rid}" Type="{rtype}" Target="{target}"/>' for rid, rtype, target in rels
        )
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{body}
</Relationships>
"""


def add_title_slide(deck: Deck) -> None:
    s = Slide(deck, "", number=1)
    deck.slides.append(s)
    s.add_rect(0, 0, 13.333, 7.5, fill="F3F7F9", line=None)
    s.add_rect(0, 0, 13.333, 0.16, fill=TEAL, line=None)
    s.add_text(0.75, 1.35, 11.5, 0.85, [{"text": "工作进展汇报", "size": 38, "bold": True, "color": INK}], margin=0.02)
    s.add_text(0.78, 2.27, 11.2, 0.65, [{"text": "故障演化采样系统区分度与 YS-EC588 板卡适配成果", "size": 24, "bold": True, "color": TEAL}], margin=0.02)
    s.add_text(0.82, 3.1, 10.8, 0.7, [{"text": "围绕当前系统与专利 HAVFS 的差异化，以及亿晟科技 YS-EC588 工业级安卓/鸿蒙兼容主板上的已完成工作、成果与资源需求展开。", "size": 16, "color": MUTED}], margin=0.02)
    chips = [("算法差异化", SOFT_TEAL, TEAL), ("板卡实测", SOFT_BLUE, BLUE), ("工程闭环", SOFT_AMBER, AMBER)]
    x = 0.82
    for text, fill, color in chips:
        s.add_text(x, 4.12, 1.55, 0.42, [{"text": text, "size": 13, "bold": True, "color": color, "align": "c"}], fill=fill, line=None, radius=True, valign="mid")
        x += 1.78
    s.add_card(
        0.82,
        5.0,
        3.8,
        1.25,
        "汇报重点",
        ["区分当前系统与专利 HAVFS 的技术中心", "呈现 YS-EC588 上的真实采集与评估成果"],
        fill=WHITE,
        accent=TEAL,
        bullet_size=11,
    )
    s.add_card(
        4.9,
        5.0,
        3.8,
        1.25,
        "当前结论",
        ["系统已形成采集、缓存、上传、展示、评估闭环", "下一阶段需要厂商权限、工具链、模型与联调环境"],
        fill=WHITE,
        accent=BLUE,
        bullet_size=11,
    )
    s.add_text(9.2, 5.12, 3.25, 0.8, [{"text": "2026-04-28", "size": 22, "bold": True, "color": INK, "align": "r"}, {"text": "Graduation Project", "size": 12, "color": MUTED, "align": "r"}], margin=0.02)


def build_deck() -> Deck:
    deck = Deck()
    eval_chart = deck.add_media(make_eval_chart())
    npu_chart = deck.add_media(make_npu_chart())

    # 1
    add_title_slide(deck)

    # 2
    s = Slide(deck, "本次汇报的两个问题", "汇报结构", number=2)
    deck.slides.append(s)
    s.header()
    s.add_card(
        0.8,
        1.55,
        5.75,
        4.65,
        "1. 当前系统与专利 HAVFS 有何不同",
        [
            "专利 HAVFS 的中心是多指标风险建模与频率映射",
            "当前系统的中心应切换为字段分层、资源预算、队列反馈与可靠执行",
            "区分度来自问题定义、控制变量、状态机、执行闭环和实验指标的整体替换",
        ],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=14,
    )
    s.add_card(
        6.85,
        1.55,
        5.75,
        4.65,
        "2. YS-EC588 上已完成工作与后续资源",
        [
            "完成 OpenHarmony HDC 与 Rockchip sysfs/debugfs 两条 NPU 采集后端",
            "形成真实板卡采集、轨迹回放、事件标注、评估报告与前后端展示链路",
            "明确继续推进需要的权限、工具链、模型负载、传感器规格和联调条件",
        ],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=14,
    )

    # 3
    s = Slide(deck, "专利 HAVFS 的核心逻辑", "一、与专利 HAVFS 的区分度", number=3)
    deck.slides.append(s)
    s.header()
    steps = [
        ("在线基线化", "动态均值、尺度、差分与波动速度"),
        ("四分量风险", "异常 / 突变 / 压力 / 漂移"),
        ("频率映射", "风险融合后经 Sigmoid 映射"),
        ("滞回状态机", "STABLE / EXPLORE / ALERT"),
        ("探索与缓冲", "随机高频抽查与前后窗口保存"),
    ]
    x = 0.65
    for i, (title, desc) in enumerate(steps):
        s.add_text(x, 1.8, 2.18, 1.45, [{"text": f"{i + 1}", "size": 24, "bold": True, "color": TEAL, "align": "c"}, {"text": title, "size": 15, "bold": True, "color": INK, "align": "c"}, {"text": desc, "size": 10, "color": MUTED, "align": "c"}], fill=WHITE, line=LINE, radius=True, valign="mid", margin=0.05)
        if i < len(steps) - 1:
            s.add_text(x + 2.15, 2.25, 0.42, 0.38, [{"text": "→", "size": 18, "bold": True, "color": MUTED, "align": "c"}], margin=0.0, valign="mid")
        x += 2.48
    s.add_card(
        1.05,
        4.25,
        5.45,
        1.45,
        "专利方案优势",
        ["风险建模完整，关注故障前后高质量数据", "逻辑链条清楚，适合从算法角度描述采样频率"],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=12,
    )
    s.add_card(
        6.85,
        4.25,
        5.45,
        1.45,
        "专利方案工程短板",
        ["参数多、依赖指标完备，迁移和调参成本高", "边端缓存、上传背压、多设备冲突没有成为主要创新点"],
        fill=SOFT_AMBER,
        accent=AMBER,
        bullet_size=12,
    )

    # 4
    s = Slide(deck, "当前系统的重新定位", "一、与专利 HAVFS 的区分度", number=4)
    deck.slides.append(s)
    s.header()
    s.add_text(
        0.85,
        1.4,
        11.7,
        0.75,
        [{"text": "不是“简化版 HAVFS”，而是面向边端资源受限的分层字段自适应采集与可靠执行框架。", "size": 22, "bold": True, "color": TEAL, "align": "c"}],
        fill=SOFT_TEAL,
        line=None,
        radius=True,
        valign="mid",
    )
    cards = [
        ("三类控制量", ["evolution_score / urgency", "field_priority_score", "execution_pressure_score"], TEAL, SOFT_TEAL),
        ("相位驱动控制", ["聚焦采样", "恢复观测", "巡航巡检", "边端降级"], BLUE, SOFT_BLUE),
        ("可靠执行链路", ["RingBuffer", "SQLite WAL outbox", "HTTP 批量上传 / 重试"], AMBER, SOFT_AMBER),
    ]
    x = 0.85
    for title, bullets, accent, fill in cards:
        s.add_card(x, 2.65, 3.75, 2.6, title, bullets, fill=fill, accent=accent, bullet_size=13)
        x += 4.05
    s.add_text(
        1.1,
        5.78,
        11.2,
        0.62,
        [{"text": "区分度关键：把“风险数值映射到频率”的单闭环，改为“状态 + 字段 + 系统负载 + 传输状态”的联合调度。", "size": 16, "bold": True, "color": INK, "align": "c"}],
        fill=WHITE,
        line=LINE,
        radius=True,
        valign="mid",
    )

    # 5
    s = Slide(deck, "关键差异对照", "一、与专利 HAVFS 的区分度", number=5)
    deck.slides.append(s)
    s.header()
    s.add_table(
        0.55,
        1.35,
        [1.65, 5.15, 5.15],
        0.62,
        ["维度", "专利 HAVFS", "当前系统 / 建议表述"],
        [
            ["问题中心", "提高故障前后数据质量，强调风险建模完整性", "边端受限场景下稳定采、存、传，风险只是调度输入之一"],
            ["输入假设", "默认多指标持续可得，温度/功耗/ECC 等较完整", "缺失可容忍，核心快字段必采，慢字段按需补采"],
            ["控制变量", "异常、突变、压力、漂移四分量", "紧迫度、字段优先级、执行压力，后续可加入传输背压"],
            ["控制器", "风险融合后 Sigmoid 映射到采样频率", "相位驱动 + 字段策略 + 传输策略联合输出"],
            ["状态机", "STABLE / EXPLORE / ALERT，含随机探索", "巡航 / 聚焦 / 恢复 / 降级，强调确定性和工程可复现"],
            ["执行机制", "告警前后窗口缓冲为主", "RingBuffer + SQLite WAL + 异步上传 + 多设备调度"],
        ],
        font_size=9,
    )

    # 6
    s = Slide(deck, "区分度一：控制变量换核", "一、与专利 HAVFS 的区分度", number=6)
    deck.slides.append(s)
    s.header()
    s.add_card(
        0.8,
        1.55,
        5.4,
        3.7,
        "专利 HAVFS：四分量风险闭环",
        [
            "异常程度、突变程度、压力程度、漂移程度",
            "权重融合为总风险，再映射到采样频率",
            "结构清楚，但与原方案相似性强，参数解释成本高",
        ],
        fill=SOFT_AMBER,
        accent=AMBER,
        bullet_size=14,
    )
    s.add_text(6.15, 3.0, 0.8, 0.5, [{"text": "→", "size": 22, "bold": True, "color": MUTED, "align": "c"}], valign="mid")
    s.add_card(
        7.0,
        1.55,
        5.45,
        3.7,
        "当前系统：多目标调度变量",
        [
            "紧迫度：负载、温度、错误、设备不可用",
            "字段优先级：慢字段刷新需求与信息收益",
            "执行压力：outbox、死信、环形缓冲、上传回压",
        ],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=14,
    )
    s.add_text(
        1.1,
        5.75,
        11.2,
        0.62,
        [{"text": "表达重心从“调一个风险公式”变为“在资源、字段、传输约束下做在线采样调度”。", "size": 17, "bold": True, "color": INK, "align": "c"}],
        fill=WHITE,
        line=LINE,
        radius=True,
        valign="mid",
    )

    # 7
    s = Slide(deck, "区分度二：字段分层成为主创新点", "一、与专利 HAVFS 的区分度", number=7)
    deck.slides.append(s)
    s.header()
    s.add_table(
        0.75,
        1.45,
        [2.1, 4.9, 4.9],
        0.72,
        ["字段层级", "典型字段", "调度策略"],
        [
            ["快字段", "utilization、chip_temp_c、power_w、status、error、throttle_flag", "每轮优先采集，承担高频保活和异常触发"],
            ["慢字段", "freq_mhz、pcie_rx/tx、ECC、threads、cache、device_reset_count", "聚焦 / 恢复 / 巡检时补采；边端压力高时压缩"],
            ["输出策略", "phase、field_policy、sampled_slow、transport_policy", "每轮不只决定多久采，还决定采哪些字段、如何上传"],
        ],
        font_size=12,
    )
    s.add_card(
        0.95,
        4.55,
        5.45,
        1.35,
        "与 HAVFS 的不同",
        ["HAVFS 主要做设备级频率调节", "当前系统做字段级采样成本控制"],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=13,
    )
    s.add_card(
        6.85,
        4.55,
        5.45,
        1.35,
        "对论文/汇报的价值",
        ["可以解释为什么稳定期仍保留关键字段", "也能解释为什么关键窗口集中补采慢字段"],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=13,
    )

    # 8
    s = Slide(deck, "区分度三：边端可靠执行链路进入算法", "一、与专利 HAVFS 的区分度", number=8)
    deck.slides.append(s)
    s.header()
    pipeline = [
        ("Adapter", "CPU/GPU/NPU\nReplay"),
        ("Sampler", "快字段\n慢字段"),
        ("Scheduler", "phase\npolicy"),
        ("RingBuffer", "短时吸峰"),
        ("SQLite WAL", "持久队列\n失败重试"),
        ("Uploader", "批量压缩\n异步上送"),
        ("Backend", "入库查询\n前端展示"),
    ]
    x = 0.5
    for i, (title, desc) in enumerate(pipeline):
        s.add_text(x, 1.65, 1.55, 1.2, [{"text": title, "size": 13, "bold": True, "color": TEAL, "align": "c"}, {"text": desc, "size": 9, "color": INK, "align": "c"}], fill=WHITE, line=LINE, radius=True, valign="mid", margin=0.04)
        if i < len(pipeline) - 1:
            s.add_text(x + 1.48, 2.04, 0.32, 0.36, [{"text": "→", "size": 14, "bold": True, "color": MUTED, "align": "c"}], valign="mid", margin=0.0)
        x += 1.82
    s.add_card(
        0.85,
        3.55,
        3.8,
        1.65,
        "工程机制",
        ["采样与上传解耦", "本地 WAL 保证断网/失败后可重试", "死信控制避免无限重试拖垮系统"],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=11,
    )
    s.add_card(
        4.85,
        3.55,
        3.8,
        1.65,
        "算法反馈",
        ["execution_pressure_score 反映 outbox 与缓冲压力", "传输积压可触发降级与保留关键字段"],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=11,
    )
    s.add_card(
        8.85,
        3.55,
        3.8,
        1.65,
        "差异化表达",
        ["不是单纯输出 interval", "而是输出 interval + phase + field_policy + transport_policy"],
        fill=SOFT_AMBER,
        accent=AMBER,
        bullet_size=11,
    )

    # 9
    s = Slide(deck, "阶段性实验结果：证明系统特征", "一、与专利 HAVFS 的区分度", number=9)
    deck.slides.append(s)
    s.header()
    s.add_image(eval_chart, 0.65, 1.38, 7.1, 3.88)
    s.add_card(
        8.05,
        1.45,
        4.5,
        1.05,
        "冗余率下降",
        ["29.82% → 20.00%，低信息量重复采样减少约 32.9%"],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=12,
    )
    s.add_card(
        8.05,
        2.75,
        4.5,
        1.05,
        "响应更快",
        ["P50 延迟 2.079s → 1.109s；P95 延迟 3.488s → 2.616s"],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=12,
    )
    s.add_card(
        8.05,
        4.05,
        4.5,
        1.2,
        "边端链路参与",
        ["缓冲上传占比 62.67%，CPU 平均开销约 1.06%，内存约 66MB"],
        fill=SOFT_AMBER,
        accent=AMBER,
        bullet_size=12,
    )
    s.add_text(1.0, 5.85, 11.4, 0.5, [{"text": "说明：故障演化采样在关键窗口主动增加采样点，因此评价重点不是“采样点绝对更少”，而是冗余更低、响应更快、关键字段更集中。", "size": 13, "color": MUTED, "align": "c"}], margin=0.02)

    # 10
    s = Slide(deck, "YS-EC588 板卡工作总览", "二、YS-EC588 已完成工作与成果", number=10)
    deck.slides.append(s)
    s.header()
    works = [
        ("环境接入", "HDC / OpenHarmony 目标识别，调通远程 shell 与指标读取"),
        ("NPU 适配", "实现 OpenHarmony HDC 与 Rockchip sysfs/debugfs 两套后端"),
        ("统一模型", "映射到 XPU 字段：util、temp、freq、pstate、status 等"),
        ("真实采集", "生成 metrics / events / outbox，形成 RK3588 NPU 真实轨迹"),
        ("回放评估", "真实轨迹转 replay profile，做 fixed / evolution 对照"),
        ("系统闭环", "接入 EdgeAgent、FastAPI 后端、前端页面和报告图表"),
    ]
    positions = [(0.75, 1.45), (4.75, 1.45), (8.75, 1.45), (0.75, 3.85), (4.75, 3.85), (8.75, 3.85)]
    for (title, desc), (x, y) in zip(works, positions):
        s.add_card(x, y, 3.45, 1.55, title, [desc], fill=WHITE, accent=TEAL if y < 3 else BLUE, title_size=16, bullet_size=11)

    # 11
    s = Slide(deck, "YS-EC588 / RK3588 NPU 适配细节", "二、YS-EC588 已完成工作与成果", number=11)
    deck.slides.append(s)
    s.header()
    s.add_card(
        0.75,
        1.35,
        5.75,
        4.8,
        "采集路径",
        [
            "hdc shell cat /sys/kernel/debug/rknpu/load",
            "/sys/class/devfreq/*npu*/cur_freq",
            "available_frequencies、governor",
            "thermal_zone*/temp",
            "rknpu/reset、rknpu/version、compatible",
        ],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=13,
    )
    s.add_card(
        6.85,
        1.35,
        5.75,
        4.8,
        "已落地字段",
        [
            "utilization / core_utilization",
            "chip_temp_c",
            "freq_mhz / freq_cap_mhz / pstate",
            "throttle_flag / throttle_cause",
            "device_reset_count / status / error",
            "vendor=Rockchip，model_name=RK3588 NPU",
        ],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=13,
    )
    s.add_text(1.05, 6.22, 11.4, 0.42, [{"text": "代码产物：core/adapter/npu/backends/openharmony_hdc_backend.py 与 rockchip_sysfs_backend.py", "size": 12, "color": MUTED, "align": "c"}], margin=0.02)

    # 12
    s = Slide(deck, "真实板卡采集成果", "二、YS-EC588 已完成工作与成果", number=12)
    deck.slides.append(s)
    s.header()
    s.add_image(npu_chart, 0.65, 1.3, 7.05, 3.85)
    metrics = [
        ("178 条", "有效 NPU 记录"),
        ("178.62 s", "连续采集时长"),
        ("37.923-43.461°C", "芯片温度范围"),
        ("1000 MHz", "NPU 频率观测"),
        ("36 次", "慢字段补采"),
        ("status=ok", "无采集错误"),
    ]
    x0, y0 = 8.0, 1.35
    for idx, (num, label) in enumerate(metrics):
        x = x0 + (idx % 2) * 2.25
        y = y0 + (idx // 2) * 1.22
        s.add_text(x, y, 2.05, 0.88, [{"text": num, "size": 18, "bold": True, "color": TEAL, "align": "c"}, {"text": label, "size": 10, "color": MUTED, "align": "c"}], fill=WHITE, line=LINE, radius=True, valign="mid")
    s.add_card(
        8.0,
        5.25,
        4.35,
        1.0,
        "数据资产",
        ["real_npu_raw_metrics.csv / .db", "real_npu_trace_20260425.csv + 事件标注"],
        fill=SOFT_AMBER,
        accent=AMBER,
        bullet_size=10,
    )

    # 13
    s = Slide(deck, "YS-EC588 工作成果归档", "二、YS-EC588 已完成工作与成果", number=13)
    deck.slides.append(s)
    s.header()
    s.add_table(
        0.55,
        1.35,
        [2.05, 4.9, 5.25],
        0.62,
        ["类别", "成果", "对应产物"],
        [
            ["板卡适配", "OpenHarmony HDC、Rockchip sysfs/debugfs NPU 后端", "openharmony_hdc_backend.py / rockchip_sysfs_backend.py"],
            ["采集数据", "真实 RK3588 NPU metrics、events、outbox", "experiments/npu_capture/real_npu_raw_*"],
            ["回放资产", "将真实 NPU 采样整理为可复现实验轨迹", "real_npu_trace_20260425.csv / events"],
            ["事件标注", "workload_start、sustained_compute、thermal_accumulation、late_stage_pressure", "real_npu_events_20260425.csv"],
            ["实验评估", "fixed 与 evolution 对照，输出报告和图表", "experiments/thesis_eval_20260426/report"],
            ["系统集成", "边端代理、后端 API、前端 Dashboard/Alert/Control", "core/runtime、backend/app、frontend/src"],
        ],
        font_size=9,
    )

    # 14
    s = Slide(deck, "继续开展工作需要的资源：板卡与系统权限", "三、资源需求", number=14)
    deck.slides.append(s)
    s.header()
    s.add_card(
        0.8,
        1.4,
        3.75,
        4.55,
        "工程镜像与访问权限",
        [
            "Android / OpenHarmony / Linux BSP 镜像与切换说明",
            "root、hdc/adb、debugfs 挂载权限",
            "开放 rknpu、devfreq、thermal、日志节点",
            "内核配置、驱动版本和系统恢复流程",
        ],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=12,
    )
    s.add_card(
        4.85,
        1.4,
        3.75,
        4.55,
        "NPU 驱动与工具链",
        [
            "RKNN runtime、rknn_server、模型转换工具",
            "NPU 性能计数器、负载、频率、限频含义文档",
            "示例推理程序、矩阵乘或压力测试 demo",
            "驱动日志、错误码、固件版本说明",
        ],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=12,
    )
    s.add_card(
        8.9,
        1.4,
        3.75,
        4.55,
        "硬件与恢复条件",
        [
            "备用板卡、稳定电源、散热方案",
            "串口/UART/JTAG 调试线和接线定义",
            "可刷回的 recovery 包与操作手册",
            "允许进行热压力、断网、重启恢复实验的边界",
        ],
        fill=SOFT_AMBER,
        accent=AMBER,
        bullet_size=12,
    )

    # 15
    s = Slide(deck, "继续开展工作需要的资源：测试与联调条件", "三、资源需求", number=15)
    deck.slides.append(s)
    s.header()
    s.add_table(
        0.7,
        1.35,
        [2.4, 4.5, 5.0],
        0.72,
        ["资源类型", "希望对方提供", "用途"],
        [
            ["模型与负载", "可长时间运行的 RKNN 模型、推理 demo、典型业务负载", "制造可复现的 NPU 高负载、热积累和限频场景"],
            ["传感器规格", "温度/功耗/频率/限频阈值含义，传感器与板级位置映射", "解释采集值，避免把平台限制误判为算法现象"],
            ["联调接口", "云端接收地址、认证方式、字段约束、日志回传接口", "验证边端上传、断网缓存、恢复重传和后端展示"],
            ["评价标准", "目标采样间隔、CPU/内存开销上限、断网保留时长、延迟 P95 要求", "形成可验收的实验协议和进展汇报口径"],
            ["技术支持", "驱动/系统/硬件联系人，问题复现所需日志模板", "缩短板卡异常、权限缺失、指标异常时的定位周期"],
        ],
        font_size=11,
    )

    # 16
    s = Slide(deck, "下一步计划与汇报结论", "结论", number=16)
    deck.slides.append(s)
    s.header()
    s.add_card(
        0.8,
        1.4,
        5.75,
        2.2,
        "本阶段结论",
        [
            "算法区分度：从 HAVFS 的多指标风险闭环，转向字段分层 + 预算约束 + 队列反馈 + 可靠执行",
            "板卡成果：YS-EC588 上已经完成 NPU 指标采集、真实轨迹、事件标注和实验报告",
            "工程闭环：边端代理、SQLite WAL、上传链路、后端接口、前端展示已经贯通",
        ],
        fill=SOFT_TEAL,
        accent=TEAL,
        bullet_size=12,
    )
    s.add_card(
        6.85,
        1.4,
        5.75,
        2.2,
        "下一步计划",
        [
            "用新命名和新控制变量完成论文算法表述，弱化 HAVFS 命名依赖",
            "接入厂商模型、驱动和权限，补齐高负载、热压力、限频、断网恢复实验",
            "把 outbox 队列反馈更深入纳入调度器，形成端到端闭环评价",
        ],
        fill=SOFT_BLUE,
        accent=BLUE,
        bullet_size=12,
    )
    s.add_text(
        1.0,
        4.55,
        11.35,
        1.05,
        [{"text": "最终汇报口径", "size": 17, "bold": True, "color": TEAL, "align": "c"}, {"text": "当前系统是一套面向异构边端设备的分层字段自适应采集与可靠执行框架，YS-EC588 是该框架在工业级安卓/鸿蒙兼容主板上的实测验证载体。", "size": 16, "bold": True, "color": INK, "align": "c"}],
        fill=WHITE,
        line=LINE,
        radius=True,
        valign="mid",
    )
    return deck


def content_types_xml(slide_count: int) -> str:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  {slide_overrides}
</Types>
"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def presentation_xml(slide_count: int) -> str:
    slide_ids = "\n".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, slide_count + 1))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle>
    <a:defPPr><a:defRPr lang="zh-CN"><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/></a:defRPr></a:defPPr>
  </p:defaultTextStyle>
</p:presentation>
"""


def presentation_rels_xml(slide_count: int) -> str:
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for i in range(1, slide_count + 1):
        rels.append(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(rels)}
</Relationships>
"""


def slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle><a:lvl1pPr><a:defRPr sz="3200"><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/></a:defRPr></a:lvl1pPr></p:titleStyle>
    <p:bodyStyle><a:lvl1pPr><a:defRPr sz="1800"><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/></a:defRPr></a:lvl1pPr></p:bodyStyle>
    <p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/></a:defRPr></a:lvl1pPr></p:otherStyle>
  </p:txStyles>
</p:sldMaster>
"""


def slide_master_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"""


def slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def slide_layout_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"""


def theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="ProgressTheme">
  <a:themeElements>
    <a:clrScheme name="Progress">
      <a:dk1><a:srgbClr val="1F2937"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="334155"/></a:dk2><a:lt2><a:srgbClr val="F7F9FB"/></a:lt2>
      <a:accent1><a:srgbClr val="0F766E"/></a:accent1><a:accent2><a:srgbClr val="2563EB"/></a:accent2>
      <a:accent3><a:srgbClr val="B45309"/></a:accent3><a:accent4><a:srgbClr val="15803D"/></a:accent4>
      <a:accent5><a:srgbClr val="64748B"/></a:accent5><a:accent6><a:srgbClr val="CBD5E1"/></a:accent6>
      <a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Microsoft YaHei">
      <a:majorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/></a:majorFont>
      <a:minorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Microsoft YaHei"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="ProgressFmt">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:gradFill rotWithShape="1"><a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"/></a:gs><a:gs pos="100000"><a:schemeClr val="phClr"/></a:gs></a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="25400"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="38100"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/><a:extraClrSchemeLst/>
</a:theme>
"""


def app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>{slide_count}</Slides>
  <Notes>0</Notes>
  <HiddenSlides>0</HiddenSlides>
  <ScaleCrop>false</ScaleCrop>
  <Company></Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>
"""


def core_xml() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>工作进展汇报：故障演化采样与 YS-EC588 成果</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def write_pptx(deck: Deck, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        slide_count = len(deck.slides)
        zf.writestr("[Content_Types].xml", content_types_xml(slide_count))
        zf.writestr("_rels/.rels", root_rels_xml())
        zf.writestr("docProps/app.xml", app_xml(slide_count))
        zf.writestr("docProps/core.xml", core_xml())
        zf.writestr("ppt/presentation.xml", presentation_xml(slide_count))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels_xml(slide_count))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels_xml())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels_xml())
        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        for idx, slide in enumerate(deck.slides, start=1):
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide.xml())
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide.rels_xml())
        for media in deck.media:
            zf.writestr(f"ppt/media/{media.name}", media.data)


def main() -> None:
    deck = build_deck()
    write_pptx(deck, OUT)
    with zipfile.ZipFile(OUT, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"Bad zip member: {bad}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
