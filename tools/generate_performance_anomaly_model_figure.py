from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures" / "性能异常检测与类型识别模型图.png"
FONT_REG = "C:/Windows/Fonts/Noto Sans SC (TrueType).otf"
FONT_BOLD = "C:/Windows/Fonts/Noto Sans SC Bold (TrueType).otf"

W, H = 1080, 1404
INK = (20, 20, 20)
MUTED = (95, 95, 95)
LIGHT = (248, 248, 248)
BLUE = (35, 75, 120)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


F_TITLE = font(35, True)
F_SECTION = font(25, True)
F_BOX = font(24)
F_SMALL = font(20)
F_TINY = font(18)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont):
    box = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=5)
    return box[2] - box[0], box[3] - box[1]


def center_text(draw, rect, text, fnt, fill=INK, spacing=5):
    x1, y1, x2, y2 = rect
    tw, th = text_size(draw, text, fnt)
    draw.multiline_text(
        (x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2),
        text,
        font=fnt,
        fill=fill,
        align="center",
        spacing=spacing,
    )


def box(draw, rect, text, fnt=F_BOX, width=3, fill=WHITE, outline=INK, radius=12):
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)
    center_text(draw, rect, text, fnt)


def group_box(draw, rect, title, fnt=F_SECTION, width=3, fill=LIGHT, outline=INK, radius=12):
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=outline, width=width)
    x1, y1, _, _ = rect
    draw.text((x1 + 20, y1 + 12), title, font=fnt, fill=INK)


def arrow(draw, start, end, width=3, fill=INK):
    draw.line([start, end], fill=fill, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(y2 - y1) >= abs(x2 - x1):
        sign = 1 if y2 > y1 else -1
        pts = [(x2, y2), (x2 - 9, y2 - sign * 17), (x2 + 9, y2 - sign * 17)]
    else:
        sign = 1 if x2 > x1 else -1
        pts = [(x2, y2), (x2 - sign * 17, y2 - 9), (x2 - sign * 17, y2 + 9)]
    draw.polygon(pts, fill=fill)


def plus(draw, center, radius=18):
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=WHITE, outline=BLUE, width=3)
    draw.line((x - 11, y, x + 11, y), fill=INK, width=3)
    draw.line((x, y - 11, x, y + 11), fill=INK, width=3)


def main():
    scale = 2
    img = Image.new("RGB", (W * scale, H * scale), WHITE)
    draw = ImageDraw.Draw(img)

    def srect(r):
        return tuple(int(v * scale) for v in r)

    def spt(p):
        return tuple(int(v * scale) for v in p)

    global F_TITLE, F_SECTION, F_BOX, F_SMALL, F_TINY
    F_TITLE = font(35 * scale, True)
    F_SECTION = font(25 * scale, True)
    F_BOX = font(24 * scale)
    F_SMALL = font(20 * scale)
    F_TINY = font(18 * scale)

    def b(rect, text, fnt=F_BOX, fill=WHITE, radius=12, width=3):
        box(draw, srect(rect), text, fnt, width=width * scale, fill=fill, radius=radius * scale)

    def g(rect, title, fnt=F_SECTION, fill=LIGHT, radius=12, width=3):
        group_box(draw, srect(rect), title, fnt, width=width * scale, fill=fill, radius=radius * scale)

    def ct(rect, text, fnt, fill=INK):
        center_text(draw, srect(rect), text, fnt, fill=fill, spacing=5 * scale)

    def ar(a, c, width=3, fill=INK):
        arrow(draw, spt(a), spt(c), width=width * scale, fill=fill)

    def pl(c, radius=18):
        plus(draw, spt(c), radius=radius * scale)

    # Title.
    ct((20, 16, 1060, 70), "XPU-NeuFD 性能异常检测与类型识别模型", F_TITLE)

    # Final result layer.
    b((210, 92, 870, 162), "最终输出：正常状态 / 性能异常类型 / 解释信息", F_SECTION, fill=LIGHT)
    ct((220, 164, 860, 218), "高负载、存储饱和、频率受限、I/O/总线瓶颈等可观测性能异常", F_SMALL, fill=MUTED)

    # Explainability layer.
    g((95, 246, 985, 356), "推理与解释机制")
    expl = [
        ((130, 286, 330, 334), "时间步误差\n定位异常窗口"),
        ((440, 286, 640, 334), "特征贡献度\n定位关键指标"),
        ((750, 286, 950, 334), "类型置信度\n输出异常语义"),
    ]
    for r, t in expl:
        b(r, t, F_TINY, fill=WHITE, radius=8, width=2)
        ar(((r[0] + r[2]) / 2, 246), ((r[0] + r[2]) / 2, r[1]))

    ar((540, 356), (540, 246))
    ar((540, 218), (540, 162))

    # Multi-task heads.
    g((35, 402, 1045, 608), "多任务输出层")
    heads = [
        ((70, 454, 275, 516), "状态预测头\n预测下一时刻指标"),
        ((315, 454, 520, 516), "特征重构头\n重构当前窗口"),
        ((560, 454, 765, 516), "异常检测头\n输出异常概率"),
        ((805, 454, 1010, 516), "类型识别头\n匹配左侧异常表"),
    ]
    for r, t in heads:
        b(r, t, F_TINY, radius=9, width=2)
        ar(((r[0] + r[2]) / 2, 608), ((r[0] + r[2]) / 2, r[3]))

    # Feature trunk.
    b((245, 650, 835, 725), "共享时序特征 H", F_SECTION, fill=LIGHT)
    ar((540, 725), (540, 608))

    g((260, 765, 820, 1054), "TCN 膨胀卷积时序建模")
    tcn_boxes = [
        ((420, 820, 660, 866), "Dilated Conv1d"),
        ((420, 884, 660, 930), "GELU"),
        ((420, 948, 660, 994), "残差连接 + LayerNorm"),
    ]
    for r, t in tcn_boxes:
        b(r, t, F_SMALL, radius=8, width=2)
    ct((286, 858, 386, 944), "N×", F_SECTION)
    ar((540, 994), (540, 948))
    ar((540, 930), (540, 884))
    ar((540, 866), (540, 820))
    ar((540, 765), (540, 725))

    # Encoding layer.
    g((185, 1100, 895, 1272), "输入编码与时间嵌入")
    b((235, 1194, 425, 1236), "特征门控", F_SMALL, radius=8, width=2)
    b((235, 1140, 425, 1182), "线性投影", F_SMALL, radius=8, width=2)
    b((655, 1168, 845, 1220), "Time2Vec\n时间编码", F_SMALL, radius=8, width=2)
    pl((540, 1160), radius=18)
    ar((330, 1194), (330, 1182))
    ar((425, 1160), (522, 1160))
    ar((655, 1194), (558, 1168))
    ar((540, 1142), (540, 1054))

    # Inputs.
    b((65, 1320, 395, 1382), "XPU 统一监测字段 X\n利用率/温度/功耗/频率/存储/I/O/错误", F_TINY, radius=9, width=2)
    b((430, 1320, 645, 1382), "缺失掩码 M\n标记有效字段", F_TINY, radius=9, width=2)
    b((680, 1320, 1015, 1382), "采样间隔 Δt\n适配变频采集", F_TINY, radius=9, width=2)
    pl((330, 1295), radius=17)
    ar((230, 1320), (318, 1301))
    ar((538, 1320), (346, 1301))
    ar((330, 1278), (330, 1236))
    ar((848, 1320), (752, 1220))

    # Output-head links to explainability.
    for x in (172, 418, 662, 908):
        ar((x, 454), (x, 402))
    ar((540, 402), (540, 356))

    ct((45, 550, 1035, 590), "异常类型识别头的输出类别与左侧“可观测性能异常类型表”保持一致", F_TINY, fill=MUTED)

    img = img.resize((W, H), Image.Resampling.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
