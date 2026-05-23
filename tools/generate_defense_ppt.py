from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "本科毕业设计答辩PPT_自适应变频异构算力采集系统.pptx"

W = Inches(13.333)
H = Inches(7.5)

BG = RGBColor(248, 250, 252)
INK = RGBColor(30, 41, 59)
MUTED = RGBColor(100, 116, 139)
BLUE = RGBColor(37, 99, 235)
TEAL = RGBColor(13, 148, 136)
AMBER = RGBColor(217, 119, 6)
RED = RGBColor(220, 38, 38)
GREEN = RGBColor(22, 163, 74)
LINE = RGBColor(203, 213, 225)
WHITE = RGBColor(255, 255, 255)
PANEL = RGBColor(241, 245, 249)


def set_font(run, size=18, bold=False, color=INK):
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def fill_bg(slide, color=BG):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_page_no(slide, n: int):
    box = slide.shapes.add_textbox(Inches(12.35), Inches(7.05), Inches(0.55), Inches(0.22))
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = f"{n:02d}"
    set_font(r, 8, color=MUTED)


def add_top_bar(slide, title: str, part: str | None = None, n: int | None = None):
    bar = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, W, Inches(0.18))
    bar.fill.solid()
    bar.fill.fore_color.rgb = BLUE
    bar.line.fill.background()

    if part:
        tag = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(0.58),
            Inches(0.44),
            Inches(1.25),
            Inches(0.32),
        )
        tag.fill.solid()
        tag.fill.fore_color.rgb = RGBColor(219, 234, 254)
        tag.line.color.rgb = RGBColor(191, 219, 254)
        tf = tag.text_frame
        tf.clear()
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = part
        set_font(r, 10, bold=True, color=BLUE)

    title_x = Inches(0.58 if not part else 1.98)
    title_box = slide.shapes.add_textbox(title_x, Inches(0.38), Inches(10.6), Inches(0.48))
    p = title_box.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = title
    set_font(r, 22, bold=True, color=INK)

    if n is not None:
        add_page_no(slide, n)


def add_section_label(slide, text: str, x, y, w, color=TEAL):
    label = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, Inches(0.34))
    label.fill.solid()
    label.fill.fore_color.rgb = color
    label.line.fill.background()
    tf = label.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    set_font(r, 11, bold=True, color=WHITE)
    return label


def add_bullets(slide, items, x, y, w, h, font_size=17, color=INK, line_spacing=1.08):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.06)
    tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.03)
    tf.margin_bottom = Inches(0.03)
    for idx, item in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(7)
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = item
        set_font(r, font_size, color=color)
    return box


def add_card(slide, title, body, x, y, w, h, accent=BLUE, title_size=15, body_size=13):
    card = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = LINE
    card.shadow.inherit = False

    strip = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, x, y, Inches(0.08), h)
    strip.fill.solid()
    strip.fill.fore_color.rgb = accent
    strip.line.fill.background()

    tx = slide.shapes.add_textbox(x + Inches(0.22), y + Inches(0.15), w - Inches(0.35), Inches(0.33))
    p = tx.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = title
    set_font(r, title_size, bold=True, color=accent)

    if isinstance(body, list):
        add_bullets(slide, body, x + Inches(0.22), y + Inches(0.58), w - Inches(0.35), h - Inches(0.7), body_size)
    else:
        bx = slide.shapes.add_textbox(x + Inches(0.22), y + Inches(0.58), w - Inches(0.35), h - Inches(0.7))
        tf = bx.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = body
        set_font(r, body_size, color=INK)
    return card


def add_metric(slide, label, value, note, x, y, w, h, color=BLUE):
    card = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = LINE
    tf = card.text_frame
    tf.clear()
    tf.margin_left = Inches(0.14)
    tf.margin_right = Inches(0.14)
    tf.margin_top = Inches(0.12)
    p0 = tf.paragraphs[0]
    r0 = p0.add_run()
    r0.text = label
    set_font(r0, 10, bold=True, color=MUTED)
    p1 = tf.add_paragraph()
    p1.space_before = Pt(6)
    r1 = p1.add_run()
    r1.text = value
    set_font(r1, 22, bold=True, color=color)
    p2 = tf.add_paragraph()
    p2.space_before = Pt(5)
    r2 = p2.add_run()
    r2.text = note
    set_font(r2, 10, color=MUTED)
    return card


def add_table(slide, rows, x, y, w, h, font_size=10, header_color=BLUE):
    table_shape = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, h)
    table = table_shape.table
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            cell = table.cell(i, j)
            cell.text = ""
            cell.margin_left = Inches(0.04)
            cell.margin_right = Inches(0.04)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            fill = cell.fill
            fill.solid()
            fill.fore_color.rgb = header_color if i == 0 else (WHITE if i % 2 else PANEL)
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.CENTER
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = str(text)
            set_font(r, font_size, bold=(i == 0), color=(WHITE if i == 0 else INK))
    return table_shape


def add_image(slide, path: Path, x, y, w, h=None, border=True):
    if not path.exists():
        return add_placeholder(slide, f"图片待补充\n{path.name}", x, y, w, h or Inches(2.5))
    pic = slide.shapes.add_picture(str(path), x, y, width=w, height=h)
    if border:
        frame = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, pic.width, pic.height)
        frame.fill.background()
        frame.line.color.rgb = LINE
        frame.line.width = Pt(0.8)
        pic.element.getparent().remove(pic.element)
        slide.shapes._spTree.insert_element_before(pic.element, "p:extLst")
    return pic


def add_placeholder(slide, text, x, y, w, h):
    ph = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, w, h)
    ph.fill.solid()
    ph.fill.fore_color.rgb = RGBColor(255, 251, 235)
    ph.line.color.rgb = AMBER
    ph.line.dash_style = 2
    tf = ph.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    set_font(r, 16, bold=True, color=AMBER)
    return ph


def connect(slide, x1, y1, x2, y2, color=MUTED, width=1.4):
    line = slide.shapes.add_connector(1, x1, y1, x2, y2)
    line.line.color.rgb = color
    line.line.width = Pt(width)
    return line


def slide_cover(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide, RGBColor(239, 246, 255))
    top = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, W, Inches(0.22))
    top.fill.solid()
    top.fill.fore_color.rgb = BLUE
    top.line.fill.background()

    left = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, Inches(0.18), H)
    left.fill.solid()
    left.fill.fore_color.rgb = TEAL
    left.line.fill.background()

    tag = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(0.75), Inches(0.88), Inches(2.6), Inches(0.36))
    tag.fill.solid()
    tag.fill.fore_color.rgb = WHITE
    tag.line.color.rgb = RGBColor(191, 219, 254)
    p = tag.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "本科毕业设计答辩"
    set_font(r, 13, bold=True, color=BLUE)

    title = slide.shapes.add_textbox(Inches(0.75), Inches(1.58), Inches(9.6), Inches(1.25))
    tf = title.text_frame
    tf.clear()
    for idx, line in enumerate(["基于自适应变频的", "异构算力数据采集系统的设计与实现"]):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = line
        set_font(r, 30, bold=True, color=INK)

    subtitle = slide.shapes.add_textbox(Inches(0.8), Inches(3.05), Inches(8.8), Inches(0.38))
    p = subtitle.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = "Design and Implementation of an Adaptive-Frequency Heterogeneous Computing Data Collection System"
    set_font(r, 12, color=MUTED)

    info = [
        ("学院", "计算机学院（国家示范性软件学院）"),
        ("专业", "软件工程"),
        ("汇报人", "（请补充姓名）"),
        ("指导教师", "（请补充指导教师）"),
        ("时间", "2026年6月"),
    ]
    x0, y0 = Inches(0.85), Inches(4.15)
    for i, (k, v) in enumerate(info):
        y = y0 + Inches(0.43 * i)
        pbox = slide.shapes.add_textbox(x0, y, Inches(5.8), Inches(0.28))
        p = pbox.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = f"{k}：{v}"
        set_font(r, 13, color=INK)

    add_card(
        slide,
        "关键词",
        "异构算力 / 自适应变频 / 数据采集 / 故障风险 / 云边端协同",
        Inches(8.05),
        Inches(4.35),
        Inches(4.45),
        Inches(1.05),
        accent=TEAL,
        body_size=12,
    )
    return slide


def slide_agenda(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "目录", "OVERVIEW", n)
    items = [
        ("01", "研究背景与目标", "说明问题来源、系统目标和本人完成内容"),
        ("02", "需求分析与总体设计", "梳理角色场景、总体架构、模块和技术路线"),
        ("03", "核心功能实现", "展开自适应变频采样、边端可靠执行、后端与前端实现"),
        ("04", "系统测试与结果分析", "展示功能测试、回放评估、统计检验与硬件验证"),
        ("05", "总结与展望", "归纳成果、客观说明不足和后续升级方向"),
    ]
    y = Inches(1.25)
    colors = [BLUE, TEAL, AMBER, GREEN, RED]
    for i, (num, title, desc) in enumerate(items):
        x = Inches(0.9 if i % 2 == 0 else 6.95)
        yy = y + Inches(1.0 * (i // 2))
        card = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, yy, Inches(5.4), Inches(0.72))
        card.fill.solid()
        card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = LINE
        badge = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, x + Inches(0.18), yy + Inches(0.15), Inches(0.42), Inches(0.42))
        badge.fill.solid()
        badge.fill.fore_color.rgb = colors[i]
        badge.line.fill.background()
        p = badge.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = num
        set_font(r, 9, bold=True, color=WHITE)
        t = slide.shapes.add_textbox(x + Inches(0.78), yy + Inches(0.10), Inches(4.35), Inches(0.25))
        r = t.text_frame.paragraphs[0].add_run()
        r.text = title
        set_font(r, 15, bold=True, color=INK)
        d = slide.shapes.add_textbox(x + Inches(0.78), yy + Inches(0.39), Inches(4.35), Inches(0.23))
        r = d.text_frame.paragraphs[0].add_run()
        r.text = desc
        set_font(r, 10, color=MUTED)
    add_placeholder(slide, "答辩时可在本页补充学校/学院模板标识", Inches(4.45), Inches(5.28), Inches(4.45), Inches(0.78))


def slide_background(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "研究背景：异构算力监测面临的采样矛盾", "01", n)
    add_card(
        slide,
        "应用场景",
        [
            "AI训练、推理服务和边端节点中，CPU、GPU、NPU并存已较常见",
            "设备接口、指标字段和刷新节奏差异明显，难以直接统一处理",
            "监测链路不仅包含采样频率，还涉及缓存、上传、落库和展示",
        ],
        Inches(0.65),
        Inches(1.18),
        Inches(5.55),
        Inches(2.15),
        accent=BLUE,
    )
    add_card(
        slide,
        "固定频率采样的不足",
        [
            "平稳阶段容易产生低价值重复样本，增加存储和处理开销",
            "异常演化阶段可能采样不够密集，错过关键状态变化窗口",
            "全字段、全设备同步采样难以兼顾边端执行压力与响应时效",
        ],
        Inches(7.0),
        Inches(1.18),
        Inches(5.55),
        Inches(2.15),
        accent=RED,
    )
    add_section_label(slide, "论文切入点", Inches(0.85), Inches(4.05), Inches(1.35), TEAL)
    add_bullets(
        slide,
        [
            "建立CPU、GPU、NPU与回放轨迹的统一指标模型，使采集、调度、存储和展示共享同一语义。",
            "以故障风险变化过程为主线，将状态紧迫度、字段刷新优先级和边端执行压力纳入统一调度。",
            "做成可运行闭环：设备适配、分层采样、边端可靠执行、后端服务、前端展示和实验评估同步落地。",
        ],
        Inches(0.9),
        Inches(4.48),
        Inches(11.6),
        Inches(1.45),
        font_size=16,
    )
    add_metric(slide, "核心对象", "CPU / GPU / NPU", "统一接入与统一表达", Inches(0.9), Inches(6.15), Inches(2.6), Inches(0.76), BLUE)
    add_metric(slide, "核心方法", "自适应变频", "围绕故障风险调节采样", Inches(3.8), Inches(6.15), Inches(2.6), Inches(0.76), TEAL)
    add_metric(slide, "核心验证", "回放 + 实机", "含YS-EC588 NPU链路", Inches(6.7), Inches(6.15), Inches(2.6), Inches(0.76), AMBER)
    add_metric(slide, "核心输出", "报告 + 图表", "支持复现实验对照", Inches(9.6), Inches(6.15), Inches(2.6), Inches(0.76), GREEN)


def slide_goal(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "研究目标与主要工作", "01", n)
    goals = [
        ("统一模型与接口机制", "分析CPU、GPU、NPU与回放数据差异，设计静态信息、快线字段和慢线字段的统一接入方式。", BLUE),
        ("自适应变频采样方法", "基于阈值反馈、状态变化与边端负载，动态决定采样相位、字段策略、传输策略和下一轮采样间隔。", TEAL),
        ("完整系统开发与评估", "实现边端采样、缓存上传、后端入库、前端展示、回放对照和统计检验，形成端到端原型。", AMBER),
    ]
    for i, (t, b, c) in enumerate(goals):
        add_card(slide, t, b, Inches(0.75 + i * 4.18), Inches(1.18), Inches(3.78), Inches(1.75), c, body_size=12)
    add_section_label(slide, "本人完成内容", Inches(0.78), Inches(3.45), Inches(1.55), BLUE)
    add_table(
        slide,
        [
            ["方向", "已完成工作", "对应产物"],
            ["系统方案", "模块划分、数据流和部署关系设计", "论文第3-4章、架构图"],
            ["核心算法", "调度器、快慢线字段、四类相位策略", "core/scheduler、core/sampler"],
            ["可靠执行", "环形缓冲、SQLite WAL outbox、批量上传、重试", "core/runtime、core/storage"],
            ["后端前端", "FastAPI接口、React仪表盘、控制台、告警中心", "backend、frontend"],
            ["实验评估", "轨迹生成、多基线对照、统计检验和报告", "demo、experiments"],
        ],
        Inches(0.82),
        Inches(3.92),
        Inches(11.7),
        Inches(2.52),
        font_size=10,
        header_color=BLUE,
    )
    note = slide.shapes.add_textbox(Inches(0.85), Inches(6.62), Inches(11.6), Inches(0.28))
    r = note.text_frame.paragraphs[0].add_run()
    r.text = "答辩表达重点：本项目不是单点算法演示，而是围绕自适应采样构建可运行、可复现、可展示的工程闭环。"
    set_font(r, 12, bold=True, color=TEAL)


def slide_requirements(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "需求分析：角色、流程与功能边界", "02", n)
    add_table(
        slide,
        [
            ["角色", "关注重点", "典型操作"],
            ["监控观察者", "设备状态、趋势、事件与告警", "查看概览、曲线、日志、实验结果"],
            ["实验操作者", "实验组织、参数设置、报告输出", "生成轨迹、启动任务、查看报告"],
            ["系统维护者", "采样链路、服务健康和异常定位", "检查健康、缓存积压、入库与告警"],
        ],
        Inches(0.75),
        Inches(1.12),
        Inches(11.85),
        Inches(1.38),
        font_size=11,
        header_color=TEAL,
    )
    stages = ["设备状态获取", "边端采样", "调度判定", "本地缓冲与上传", "后端接收存储", "前端展示", "实验评估"]
    x0, y = Inches(0.55), Inches(3.15)
    box_w = Inches(1.55)
    for i, stage in enumerate(stages):
        x = x0 + Inches(1.82 * i)
        shp = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, box_w, Inches(0.68))
        shp.fill.solid()
        shp.fill.fore_color.rgb = WHITE
        shp.line.color.rgb = LINE
        p = shp.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = stage
        set_font(r, 10, bold=True, color=INK)
        if i < len(stages) - 1:
            connect(slide, x + box_w, y + Inches(0.34), x + Inches(1.82), y + Inches(0.34), color=BLUE)
    add_section_label(slide, "关键需求", Inches(0.75), Inches(4.35), Inches(1.25), AMBER)
    add_bullets(
        slide,
        [
            "功能需求：总览监控、实时趋势、事件日志与告警、实时采集、回放实验、报告查看和规则维护。",
            "非功能需求：基本实时性、链路可靠性、设备与字段可扩展性、模块可维护性、实验可复现性。",
            "数据需求：设备快照、历史指标、事件记录、告警规则/告警对象、实验报告五类核心对象。",
        ],
        Inches(0.82),
        Inches(4.82),
        Inches(11.7),
        Inches(1.42),
        font_size=16,
    )
    add_placeholder(slide, "可在此页右下角补充角色用例图", Inches(9.35), Inches(6.33), Inches(3.0), Inches(0.55))


def slide_architecture(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "总体架构设计：边端采集到中心展示闭环", "02", n)
    fig = ROOT / "docs" / "figures" / "图4_2_系统总体架构设计图.png"
    add_image(slide, fig, Inches(0.55), Inches(1.07), Inches(12.25), Inches(1.0))
    add_card(
        slide,
        "边端侧",
        [
            "设备适配器读取CPU、GPU、NPU或回放轨迹",
            "采样器执行快线/慢线分层采集和调度决策",
            "EdgeAgent完成异步编排、缓冲、WAL写入和上传",
        ],
        Inches(0.72),
        Inches(2.55),
        Inches(3.75),
        Inches(2.0),
        BLUE,
        body_size=11,
    )
    add_card(
        slide,
        "中心侧",
        [
            "FastAPI接收指标与事件批量上传",
            "SQLite保存设备快照、历史指标、事件、告警和规则",
            "控制服务负责轨迹生成、实时采集和回放对照任务",
        ],
        Inches(4.8),
        Inches(2.55),
        Inches(3.75),
        Inches(2.0),
        TEAL,
        body_size=11,
    )
    add_card(
        slide,
        "展示与评估侧",
        [
            "React + ECharts展示概览、趋势、事件和实验结果",
            "实验脚本输出CSV、JSON、Markdown和图像报告",
            "统一输入下对比固定频率、阈值、趋势和本文方法",
        ],
        Inches(8.88),
        Inches(2.55),
        Inches(3.75),
        Inches(2.0),
        AMBER,
        body_size=11,
    )
    add_table(
        slide,
        [
            ["设计原则", "落实方式"],
            ["统一抽象优先", "以XPUDynamicMetrics承载通用字段和设备扩展字段"],
            ["调度与采集解耦", "适配器负责采集，调度器负责相位/间隔/策略"],
            ["边端可靠优先", "环形缓冲 + SQLite WAL outbox + 批量上传 + 重试"],
            ["实验可复现", "固定随机种子、真值事件表、多基线报告"],
        ],
        Inches(1.15),
        Inches(5.06),
        Inches(11.0),
        Inches(1.55),
        font_size=10,
        header_color=BLUE,
    )


def slide_modules(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "功能模块划分与技术路线", "02", n)
    fig = ROOT / "docs" / "figures" / "图4_3_系统功能模块划分图.png"
    add_image(slide, fig, Inches(0.65), Inches(1.0), Inches(12.0), Inches(1.7))
    add_table(
        slide,
        [
            ["模块", "主要职责", "实现位置/技术"],
            ["设备适配", "CPU/GPU/NPU/回放数据统一接入", "core/adapter、core/collector"],
            ["采样调度", "四类模式、快慢线字段、相位切换", "core/scheduler、core/sampler"],
            ["可靠执行", "异步编排、环形缓冲、WAL队列、上传重试", "core/runtime、core/storage"],
            ["后端服务", "接收、查询、告警、控制、实验报告读取", "FastAPI + SQLite"],
            ["前端展示", "仪表盘、控制台、告警中心、图表渲染", "React + TypeScript + ECharts"],
            ["实验评估", "轨迹、基线运行、指标统计、图表报告", "NumPy/Pandas/Matplotlib"],
        ],
        Inches(0.72),
        Inches(3.05),
        Inches(11.9),
        Inches(3.1),
        font_size=10,
        header_color=TEAL,
    )
    add_placeholder(slide, "界面截图可在正式答辩前替换", Inches(4.85), Inches(6.38), Inches(3.8), Inches(0.48))


def slide_data_model(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "统一指标模型与数据对象设计", "02", n)
    add_card(
        slide,
        "统一静态信息",
        "device_id、device_type、vendor、model_name、driver_version、core_count 等字段描述设备身份和能力。",
        Inches(0.72),
        Inches(1.15),
        Inches(3.8),
        Inches(1.36),
        BLUE,
    )
    add_card(
        slide,
        "统一动态指标",
        "利用率、温度、功耗、频率、内存占用、总线吞吐、限频状态、错误码与采样时间等核心状态。",
        Inches(4.78),
        Inches(1.15),
        Inches(3.8),
        Inches(1.36),
        TEAL,
    )
    add_card(
        slide,
        "调度上下文",
        "采样间隔、演化分数、相位、字段策略、传输策略、紧迫度、字段优先级和执行压力。",
        Inches(8.85),
        Inches(1.15),
        Inches(3.8),
        Inches(1.36),
        AMBER,
    )
    add_table(
        slide,
        [
            ["数据对象", "主要内容", "主要作用"],
            ["设备快照", "当前状态、最近时间、当前相位和控制信息", "支撑概览页和设备列表"],
            ["历史指标", "每次采样的统一指标和调度结果", "支撑趋势、回溯和评估"],
            ["事件记录", "采集异常、设备异常、告警动作", "支撑异常定位和告警联动"],
            ["告警与规则", "规则条件、活动告警、确认/静默状态", "支撑维护和处置流程"],
            ["实验报告", "多模式结果、统计表、图像和JSON/Markdown", "支撑复现实验分析"],
        ],
        Inches(0.78),
        Inches(3.0),
        Inches(11.75),
        Inches(2.56),
        font_size=11,
        header_color=BLUE,
    )
    add_bullets(
        slide,
        [
            "设计意义：把设备差异压到适配层内部，后续调度、后端和前端均围绕统一字段工作。",
            "实事求是：当前适合毕业设计原型和单机/小规模边端验证，大规模长期运行可迁移到时序库或消息队列。",
        ],
        Inches(0.9),
        Inches(6.0),
        Inches(11.3),
        Inches(0.75),
        font_size=14,
        color=MUTED,
    )


def slide_algorithm_overview(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "核心方法：面向故障风险的自适应变频采样", "03", n)
    inputs = [
        ("设备状态", "利用率、温度、功耗、内存、限频、错误状态", BLUE),
        ("字段刷新", "快线必采、慢线补采、慢字段陈旧度", TEAL),
        ("执行压力", "outbox待发送、死信、环形缓冲积压、上传状态", AMBER),
    ]
    for i, (t, b, c) in enumerate(inputs):
        add_card(slide, t, b, Inches(0.72 + 4.08 * i), Inches(1.05), Inches(3.72), Inches(1.15), c, body_size=12)
    y = Inches(3.0)
    blocks = [
        ("紧迫度 U", "反映设备自身风险演化"),
        ("字段优先级 F", "反映慢线字段是否需要刷新"),
        ("执行压力 E", "反映边端缓存与上传压力"),
        ("控制分数", "综合决定相位和采样策略"),
    ]
    for i, (t, b) in enumerate(blocks):
        x = Inches(0.75 + 3.05 * i)
        shp = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, x, y, Inches(2.35), Inches(0.88))
        shp.fill.solid()
        shp.fill.fore_color.rgb = WHITE
        shp.line.color.rgb = LINE
        tf = shp.text_frame
        tf.clear()
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = t
        set_font(r, 14, bold=True, color=[BLUE, TEAL, AMBER, RED][i])
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = b
        set_font(r2, 9, color=MUTED)
        if i < len(blocks) - 1:
            connect(slide, x + Inches(2.35), y + Inches(0.44), x + Inches(3.05), y + Inches(0.44), BLUE)
    add_table(
        slide,
        [
            ["输出", "具体含义"],
            ["采样相位", "聚焦采样、恢复观测、巡航巡检、边端降级"],
            ["字段策略", "全量聚焦、分层补采、事件补采、快线必采等"],
            ["传输策略", "直传、缓冲上传、降级缓冲、本地缓存"],
            ["下一轮间隔", "在t_min~t_max范围内动态调整，异常阶段更密集，平稳阶段更稀疏"],
        ],
        Inches(1.0),
        Inches(4.55),
        Inches(11.3),
        Inches(1.65),
        font_size=11,
        header_color=TEAL,
    )
    note = slide.shapes.add_textbox(Inches(0.85), Inches(6.55), Inches(11.6), Inches(0.35))
    r = note.text_frame.paragraphs[0].add_run()
    r.text = "核心特点：不是简单“风险分数越高频率越高”，而是同时考虑设备风险、字段价值和边端承载能力。"
    set_font(r, 12, bold=True, color=INK)


def slide_algorithm_phase(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "调度策略：四类相位与快慢线字段", "03", n)
    add_table(
        slide,
        [
            ["采样相位", "触发依据", "字段策略", "设计目的"],
            ["聚焦采样", "异常、限频、紧迫度或控制分数高", "全量聚焦/快线必采", "提高故障窗口观测密度"],
            ["恢复观测", "风险中等或字段优先级较高", "分层补采/事件补采", "避免异常刚缓解时过早降频"],
            ["巡航巡检", "状态平稳、执行压力可控", "周期性慢线刷新", "减少低价值重复采样"],
            ["边端降级", "缓存积压或上传压力较高", "保活快线/降级缓冲", "保护边端链路稳定"],
        ],
        Inches(0.7),
        Inches(1.05),
        Inches(11.95),
        Inches(2.1),
        font_size=10,
        header_color=BLUE,
    )
    add_section_label(slide, "快线字段", Inches(0.85), Inches(3.75), Inches(1.15), TEAL)
    add_bullets(
        slide,
        [
            "利用率、温度、功耗、内存占用、状态码等高频核心字段",
            "每轮优先采集，用于快速判断设备风险变化",
        ],
        Inches(0.88),
        Inches(4.2),
        Inches(4.95),
        Inches(0.72),
        font_size=14,
    )
    add_section_label(slide, "慢线字段", Inches(6.75), Inches(3.75), Inches(1.15), AMBER)
    add_bullets(
        slide,
        [
            "频率、频率上限、总线吞吐、线程数、ECC/错误统计等扩展诊断字段",
            "按相位、陈旧度和字段优先级决定是否补采",
        ],
        Inches(6.78),
        Inches(4.2),
        Inches(4.95),
        Inches(0.72),
        font_size=14,
    )
    add_card(
        slide,
        "实现落点",
        [
            "FaultEvolutionScheduler计算U/F/E与控制分数",
            "DeviceSampler合并快线与慢线字段，并输出DeviceSample",
            "EdgeAgent把运行反馈注入调度器，实现采样与传输链路联动",
        ],
        Inches(1.08),
        Inches(5.45),
        Inches(11.1),
        Inches(1.05),
        accent=RED,
        body_size=12,
    )


def slide_edge(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "边端可靠执行：缓冲、WAL与重试机制", "03", n)
    fig = ROOT / "docs" / "figures" / "图5_5_边端可靠执行模块时序图.png"
    add_image(slide, fig, Inches(0.72), Inches(0.98), Inches(11.9), Inches(4.0))
    add_table(
        slide,
        [
            ["机制", "实现方式", "作用"],
            ["环形缓冲", "RingBuffer承接采样主循环输出", "避免上传慢阻塞采样"],
            ["持久化队列", "SQLite WAL outbox保存待发送记录", "服务不可用时保留数据"],
            ["批量上传", "HTTPUploader批量发送指标与事件", "降低请求开销"],
            ["失败重试", "attempts、next_retry_at、dead状态", "区分暂时失败和死信记录"],
        ],
        Inches(0.92),
        Inches(5.35),
        Inches(11.45),
        Inches(1.35),
        font_size=10,
        header_color=TEAL,
    )


def slide_backend_frontend(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "后端服务与前端展示实现", "03", n)
    add_card(
        slide,
        "后端 FastAPI",
        [
            "/api/ingest：接收边端批量指标和事件",
            "/api/devices、/api/metrics/history、/api/events：状态与历史查询",
            "/api/alerts/*：告警规则、活动告警、确认与静默",
            "/api/control/*：轨迹生成、回放对照、实时采集任务控制",
        ],
        Inches(0.72),
        Inches(1.05),
        Inches(5.75),
        Inches(2.25),
        BLUE,
        body_size=11,
    )
    add_card(
        slide,
        "前端 React + ECharts",
        [
            "仪表盘：设备摘要、实时趋势、最近事件、实验结果概览",
            "控制台：生成轨迹、实时采集、回放对照、任务日志",
            "告警中心：活动告警、规则维护、确认/静默/批量处置",
            "轮询刷新：不同模块按2.5~15秒周期拉取接口数据",
        ],
        Inches(6.88),
        Inches(1.05),
        Inches(5.75),
        Inches(2.25),
        TEAL,
        body_size=11,
    )
    add_image(slide, ROOT / "docs" / "figures" / "图5_7_仪表盘页面结构示意图.png", Inches(0.72), Inches(3.72), Inches(5.75), Inches(0.86))
    add_image(slide, ROOT / "docs" / "figures" / "图5_8_控制台页面结构示意图.png", Inches(6.88), Inches(3.72), Inches(5.75), Inches(0.72))
    add_placeholder(slide, "仪表盘真实运行截图待补充", Inches(0.72), Inches(5.25), Inches(5.75), Inches(1.25))
    add_placeholder(slide, "控制台/告警中心截图待补充", Inches(6.88), Inches(5.25), Inches(5.75), Inches(1.25))


def slide_experiment_design(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "测试方案：功能验证与多基线回放评估", "04", n)
    add_table(
        slide,
        [
            ["测试类别", "主要内容", "覆盖模块"],
            ["基础运行", "启动脚本、健康接口、静态页面托管", "后端、前端构建、启动脚本"],
            ["数据链路", "边端采样、入队、上传、后端接收、数据库写入", "采样器、EdgeAgent、FastAPI、SQLite"],
            ["页面功能", "仪表盘、控制台、告警中心", "React、ECharts、API"],
            ["实验链路", "轨迹生成、四类模式运行、报告输出", "demo、experiments、评估脚本"],
            ["硬件验证", "YS-EC588板端NPU实机采集", "NPU适配器、统一模型、后续处理链路"],
        ],
        Inches(0.72),
        Inches(1.05),
        Inches(11.9),
        Inches(2.25),
        font_size=10,
        header_color=BLUE,
    )
    add_card(
        slide,
        "回放实验设置",
        [
            "统一生成110 s异构回放轨迹，包含CPU、GPU、NPU三类设备和7个真值事件点",
            "对照方法：固定频率、简单阈值触发、趋势感知采样、自适应变频采样",
            "固定频率采用5 s周期；三类自适应方法使用1.0~8.0 s采样区间",
        ],
        Inches(0.86),
        Inches(3.82),
        Inches(5.55),
        Inches(1.7),
        TEAL,
        body_size=12,
    )
    add_card(
        slide,
        "评价指标",
        [
            "采样点数量、冗余率、平均采样间隔、慢线激活率、缓冲上传占比",
            "延迟P50/P95、异常捕获率、误报率、漏报率",
            "CPU平均开销、增量内存开销；8轮随机种子重复实验和统计检验",
        ],
        Inches(6.9),
        Inches(3.82),
        Inches(5.55),
        Inches(1.7),
        AMBER,
        body_size=12,
    )
    add_placeholder(slide, "此处可补充测试环境照片或运行截图", Inches(3.65), Inches(6.05), Inches(6.2), Inches(0.65))


def slide_single_result(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "测试结果：单次110 s多基线回放抽样", "04", n)
    add_table(
        slide,
        [
            ["指标", "固定频率", "阈值触发", "趋势感知", "本文方法"],
            ["采样点数量/个", "66", "52", "58", "77"],
            ["冗余率/%", "31.82", "26.92", "18.97", "20.78"],
            ["延迟P50/s", "2.1410", "0.0000", "4.0748", "0.5780"],
            ["延迟P95/s", "3.8908", "5.2017", "6.6891", "4.1685"],
            ["异常捕获率/%", "42.86", "42.86", "71.43", "100.00"],
            ["漏报率/%", "72.00", "48.00", "30.00", "11.11"],
            ["误报率/%", "2.33", "7.41", "3.70", "15.63"],
        ],
        Inches(0.72),
        Inches(1.05),
        Inches(6.15),
        Inches(3.1),
        font_size=10,
        header_color=BLUE,
    )
    add_metric(slide, "异常捕获率", "100.00%", "单次抽样中最高", Inches(7.22), Inches(1.18), Inches(2.45), Inches(1.02), GREEN)
    add_metric(slide, "漏报率", "11.11%", "明显低于三类基线", Inches(10.0), Inches(1.18), Inches(2.45), Inches(1.02), TEAL)
    add_metric(slide, "冗余率", "20.78%", "低于固定频率31.82%", Inches(7.22), Inches(2.55), Inches(2.45), Inches(1.02), BLUE)
    add_metric(slide, "采样点", "77个", "风险窗口更密集", Inches(10.0), Inches(2.55), Inches(2.45), Inches(1.02), AMBER)
    add_bullets(
        slide,
        [
            "本文方法并不单纯追求采样点总数最少，而是在异常窗口前后提高观测密度。",
            "趋势感知方法冗余率最低，但P95延迟更高；本文方法更偏向保障故障窗口覆盖。",
            "误报率相对较高，说明当前策略在异常捕获与误报控制之间选择了更积极的响应。",
        ],
        Inches(0.9),
        Inches(4.62),
        Inches(11.5),
        Inches(1.08),
        font_size=15,
    )
    add_placeholder(slide, "可补充表6-6完整表或评估报告截图", Inches(3.58), Inches(6.12), Inches(6.25), Inches(0.55))


def slide_stat_result(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "测试结果：8轮重复实验与统计检验", "04", n)
    add_table(
        slide,
        [
            ["指标均值", "固定频率", "阈值触发", "趋势感知", "本文方法"],
            ["冗余率/%", "30.62±1.63", "26.68±1.60", "19.59±2.71", "18.11±2.94"],
            ["延迟P50/s", "2.00±0.00", "0.00±0.00", "4.00±0.93", "1.13±0.69"],
            ["延迟P95/s", "3.70±0.00", "5.10±0.00", "6.64±0.08", "3.86±0.61"],
            ["异常捕获率/%", "42.86±0.00", "42.86±0.00", "71.43±0.00", "98.21±5.05"],
            ["漏报率/%", "73.08±0.00", "48.00±0.00", "30.19±1.49", "15.61±1.69"],
        ],
        Inches(0.72),
        Inches(1.05),
        Inches(6.55),
        Inches(2.65),
        font_size=9,
        header_color=TEAL,
    )
    fig = ROOT / "experiments" / "thesis_statistical" / "latest" / "seed_20260407" / "report" / "figures" / "detection_metrics.png"
    add_image(slide, fig, Inches(7.55), Inches(1.05), Inches(4.85), Inches(2.2))
    add_table(
        slide,
        [
            ["检验对象", "统计结论"],
            ["异常捕获率", "本文方法相对三类基线均显著更高，ANOVA p<0.001"],
            ["漏报率", "本文方法相对三类基线均显著更低，ANOVA p<0.001"],
            ["冗余率", "显著低于固定频率与阈值触发；与趋势感知差异未达显著"],
            ["延迟P95", "显著低于阈值触发与趋势感知；与固定频率差异未达显著"],
            ["误报率", "本文方法显著更高，需作为后续优化重点"],
        ],
        Inches(0.92),
        Inches(4.22),
        Inches(11.4),
        Inches(1.75),
        font_size=10,
        header_color=BLUE,
    )
    add_bullets(
        slide,
        [
            "总体结论：主要收益集中在异常捕获和漏报控制；冗余控制优于固定频率和简单阈值，但与趋势感知接近。",
        ],
        Inches(0.9),
        Inches(6.25),
        Inches(11.3),
        Inches(0.45),
        font_size=14,
        color=INK,
    )


def slide_ablation(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "控制量作用分析：U/F/E三类反馈的权衡", "04", n)
    add_table(
        slide,
        [
            ["变体", "冗余率/%", "延迟P50/s", "延迟P95/s", "异常捕获率/%", "漏报率/%"],
            ["完整方法 U+F+E", "18.04±1.00", "0.90±0.24", "5.25±0.59", "83.93±5.05", "23.24±0.75"],
            ["去除紧迫度 U", "17.67±1.45", "3.88±0.54", "6.02±1.04", "80.36±7.39", "29.06±2.69"],
            ["去除字段优先级 F", "15.81±0.57", "0.80±0.00", "4.15±1.17", "80.36±7.39", "18.66±0.40"],
            ["去除执行压力 E", "16.46±2.83", "1.13±0.69", "3.86±0.61", "98.21±5.05", "15.61±1.69"],
        ],
        Inches(0.72),
        Inches(1.05),
        Inches(11.95),
        Inches(2.05),
        font_size=9,
        header_color=AMBER,
    )
    add_card(
        slide,
        "观察1：紧迫度 U 是响应速度的重要来源",
        "去除U后，P50延迟从0.90 s升至3.88 s，漏报率升至29.06%，说明设备状态风险变化对采样提速有直接作用。",
        Inches(0.9),
        Inches(3.68),
        Inches(3.65),
        Inches(1.35),
        BLUE,
        body_size=11,
    )
    add_card(
        slide,
        "观察2：字段优先级 F 影响慢线补采节奏",
        "去除F后冗余率降低，但异常捕获率也下降，说明字段补采并非越少越好，需要与风险窗口覆盖共同平衡。",
        Inches(4.85),
        Inches(3.68),
        Inches(3.65),
        Inches(1.35),
        TEAL,
        body_size=11,
    )
    add_card(
        slide,
        "观察3：执行压力 E 面向工程稳态",
        "去除E后部分检测指标更激进，但系统失去对缓存与上传压力的反馈，后续需要在检测收益和链路稳定之间调参。",
        Inches(8.8),
        Inches(3.68),
        Inches(3.65),
        Inches(1.35),
        RED,
        body_size=11,
    )
    add_placeholder(slide, "可补充消融实验完整表或曲线图", Inches(3.45), Inches(5.85), Inches(6.45), Inches(0.64))


def slide_verification(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "系统验证：已实现能力与客观边界", "04", n)
    add_table(
        slide,
        [
            ["检查项", "结果", "说明"],
            ["统一启动与健康检查", "通过", "后端服务、前端构建和健康接口可用"],
            ["数据接收与持久化", "通过", "指标、事件、设备快照、告警规则可写入数据库"],
            ["监控仪表盘", "通过", "设备概览、趋势、日志和实验结果可展示"],
            ["控制台任务调度", "通过", "支持轨迹生成、实时采集、回放对照"],
            ["告警与事件联动", "通过", "支持规则、活动告警、确认和静默"],
            ["NPU实机采集", "通过", "YS-EC588主板识别npu0并完成采集链路验证"],
        ],
        Inches(0.72),
        Inches(1.05),
        Inches(11.95),
        Inches(2.55),
        font_size=10,
        header_color=GREEN,
    )
    add_card(
        slide,
        "当前结论成立范围",
        [
            "已完成端到端原型验证，可用于毕业设计范围内的演示和复现实验",
            "实验结论主要基于公开构造的回放轨迹与单一NPU板端实机接入验证",
            "不等同于面向大规模、多站点、长期在线生产监控系统的完整验证",
        ],
        Inches(0.9),
        Inches(4.18),
        Inches(5.55),
        Inches(1.72),
        BLUE,
        body_size=12,
    )
    add_card(
        slide,
        "答辩可强调的真实性",
        [
            "论文中的模块、接口、数据库对象和实验文件均能在仓库中对应到实现",
            "实验输出保留CSV、JSON、Markdown和图像，便于复核",
            "对不足保持明确说明：误报偏高、硬件覆盖不足、单机存储架构仍需扩展",
        ],
        Inches(6.9),
        Inches(4.18),
        Inches(5.55),
        Inches(1.72),
        TEAL,
        body_size=12,
    )


def slide_summary(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "总结：项目成果", "05", n)
    achievements = [
        ("统一指标建模", "CPU、GPU、NPU与回放轨迹统一映射到XPUDynamicMetrics，支撑调度、存储和前端展示。", BLUE),
        ("自适应变频采样", "基于U/F/E三类控制量实现四类相位、字段策略、传输策略和动态采样间隔。", TEAL),
        ("可靠执行链路", "环形缓冲、SQLite WAL outbox、批量上传、失败重试和死信状态已工程化落地。", AMBER),
        ("前后端闭环", "FastAPI接口、SQLite存储、React仪表盘/控制台/告警中心形成可运行系统原型。", GREEN),
        ("复现实验评估", "统一轨迹、四类基线、多轮统计检验和结构化报告支撑方法比较。", RED),
    ]
    for i, (t, b, c) in enumerate(achievements):
        x = Inches(0.72 + (i % 2) * 6.05)
        y = Inches(1.05 + (i // 2) * 1.55)
        w = Inches(5.65 if i < 4 else 11.7)
        add_card(slide, t, b, x, y, w, Inches(1.08), c, body_size=12)
    add_bullets(
        slide,
        [
            "综合测试表明：系统已经具备端到端工程可用性，并能输出可复核的实验报告。",
            "多轮实验显示：本文方法在异常捕获率和漏报率方面优势明显，但误报率较高，需要后续优化。",
        ],
        Inches(0.9),
        Inches(6.05),
        Inches(11.4),
        Inches(0.7),
        font_size=15,
    )


def slide_future(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide)
    add_top_bar(slide, "不足与后续工作", "05", n)
    rows = [
        ["不足", "当前情况", "后续改进方向"],
        ["用户与权限", "当前面向单操作者，未配置登录、鉴权和审计", "补充账号、角色权限、接口鉴权"],
        ["告警管理", "已支持基础规则和处置，交互和统计仍可深化", "完善编辑体验、分级联动、统计分析"],
        ["硬件覆盖", "NPU实机验证集中在YS-EC588单一板端", "接入更多NPU/GPU型号和负载类型"],
        ["调度泛化", "回放轨迹和局部实机验证不能覆盖全部故障模式", "引入更长时间窗口和真实负载数据"],
        ["存储传输", "SQLite + HTTP适合原型和小规模部署", "扩展消息队列、时序数据库、分布式存储"],
        ["报告展示", "报告文件完整，但前端历史报告管理较基础", "增加报告列表、图表导出和参数回显"],
    ]
    add_table(slide, rows, Inches(0.72), Inches(1.05), Inches(11.95), Inches(3.25), font_size=10, header_color=RED)
    add_card(
        slide,
        "后续总体方向",
        "在现有闭环基础上继续增强多设备兼容性、调度有效性、界面完善度和工程可扩展性，使系统逐步从毕业设计原型走向更稳定、实用的边端监测工具。",
        Inches(1.15),
        Inches(5.18),
        Inches(10.95),
        Inches(1.0),
        TEAL,
        body_size=13,
    )


def slide_qa(prs, n):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill_bg(slide, RGBColor(239, 246, 255))
    add_top_bar(slide, "谢谢各位老师", "Q&A", n)
    box = slide.shapes.add_textbox(Inches(1.35), Inches(1.65), Inches(10.6), Inches(1.0))
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "请各位老师批评指正"
    set_font(r, 34, bold=True, color=INK)

    add_card(
        slide,
        "答辩备查材料",
        [
            "论文正文：D:\\Desktop\\毕设论文.docx",
            "系统源码：backend / frontend / core / demo",
            "实验结果：experiments/thesis_statistical/latest",
            "论文配图：docs/figures",
        ],
        Inches(3.0),
        Inches(3.55),
        Inches(7.35),
        Inches(1.8),
        BLUE,
        body_size=12,
    )


def build():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    slide_cover(prs)
    builders = [
        slide_agenda,
        slide_background,
        slide_goal,
        slide_requirements,
        slide_architecture,
        slide_modules,
        slide_data_model,
        slide_algorithm_overview,
        slide_algorithm_phase,
        slide_edge,
        slide_backend_frontend,
        slide_experiment_design,
        slide_single_result,
        slide_stat_result,
        slide_ablation,
        slide_verification,
        slide_summary,
        slide_future,
        slide_qa,
    ]
    for i, builder in enumerate(builders, start=2):
        builder(prs, i)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
