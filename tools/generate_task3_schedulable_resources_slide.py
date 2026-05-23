from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
PNG_OUT = FIG_DIR / "研究任务3_KubeEdge可调度资源与指标体系.png"
LEGACY_PNG_OUT = FIG_DIR / "研究任务3_可调度资源与指标体系.png"

W, H = 1600, 900

BG = "#FFFFFF"
TEAL = "#00746B"
DARK_TEAL = "#00675F"
RED = "#C00000"
INK = "#111827"
MUTED = "#4B5563"
PANEL = "#F8FBFB"
BLUE = "#2463EB"
AMBER = "#B45309"
GREEN = "#16803C"
PURPLE = "#6D28D9"
SOFT_TEAL = "#E3F5F2"
SOFT_BLUE = "#EAF2FF"
SOFT_GREEN = "#E7F6EA"
SOFT_AMBER = "#FFF4D8"
SOFT_RED = "#FDECEC"


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


F_TITLE = font(50, True)
F_BODY = font(24)
F_BODY_B = font(24, True)
F_SMALL = font(18)
F_SMALL_B = font(20, True)
F_CARD_TITLE = font(23, True)
F_NUM = font(44, True)
F_ICON = font(19, True)
F_TINY = font(16)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=TEAL, radius=20, width=2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_chunks(draw: ImageDraw.ImageDraw, x: int, y: int, chunks: list[tuple[str, str, ImageFont.ImageFont]]) -> None:
    cx = x
    for text, color, fnt in chunks:
        draw.text((cx, y), text, font=fnt, fill=color)
        cx += draw.textbbox((0, 0), text, font=fnt)[2]


def center_text(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill=INK, spacing=5) -> None:
    lines = text.split("\n")
    bbs = [draw.textbbox((0, 0), line, font=fnt) for line in lines]
    widths = [b[2] - b[0] for b in bbs]
    heights = [b[3] - b[1] for b in bbs]
    total_h = sum(heights) + (len(lines) - 1) * spacing
    x1, y1, x2, y2 = box
    cy = y1 + (y2 - y1 - total_h) / 2
    for line, tw, th in zip(lines, widths, heights):
        draw.text((x1 + (x2 - x1 - tw) / 2, cy), line, font=fnt, fill=fill)
        cy += th + spacing


def circle_icon(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, color: str) -> None:
    draw.ellipse((x, y, x + 58, y + 58), fill=color)
    center_text(draw, (x, y, x + 58, y + 58), label, F_ICON, "#FFFFFF")


def object_card(draw, x, y, w, h, title, subtitle, color, icon_label):
    rounded(draw, (x, y, x + w, y + h), "#FFFFFF", color, radius=14, width=2)
    circle_icon(draw, x + 18, y + 8, icon_label, color)
    draw.text((x + 92, y + 13), title, font=F_CARD_TITLE, fill=color)
    draw.text((x + 92, y + 48), subtitle, font=F_SMALL, fill=INK)


def metric_card(draw, x, y, w, h, title, body, color, icon_label):
    rounded(draw, (x, y, x + w, y + h), "#FFFFFF", "#D1D5DB", radius=12, width=1)
    circle_icon(draw, x + 16, y + 16, icon_label, color)
    draw.text((x + 90, y + 14), title, font=F_CARD_TITLE, fill=color)
    draw.text((x + 90, y + 49), body, font=F_SMALL, fill=INK)


def small_pill(draw, x, y, w, title, body, fill, color):
    rounded(draw, (x, y, x + w, y + 56), fill, color, radius=12, width=2)
    draw.text((x + 18, y + 10), title, font=F_SMALL_B, fill=color)
    draw.text((x + 145, y + 11), body, font=F_SMALL, fill=INK)


def constraint_card(draw, x, y, w, h, title, body, fill, color):
    rounded(draw, (x, y, x + w, y + h), fill, color, radius=12, width=2)
    center_text(draw, (x + 8, y + 8, x + w - 8, y + 34), title, F_SMALL_B, color)
    center_text(draw, (x + 8, y + 38, x + w - 8, y + h - 8), body, F_TINY, INK)


def draw_slide() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw.text((8, 8), "3.3 研究任务3 KubeEdge可调度资源与指标体系", font=F_TITLE, fill=DARK_TEAL)
    draw.rectangle((0, 88, 242, 94), fill=DARK_TEAL)
    draw.rectangle((242, 88, W, 94), fill="#B8B8B8")

    rounded(draw, (32, 102, W - 32, 363), "#FFFFFF", TEAL, radius=18, width=2)
    draw_chunks(
        draw,
        54,
        124,
        [
            ("在 KubeEdge 框架下，边端设备首先被接入为", INK, F_BODY),
            (" Edge Node", RED, F_BODY_B),
            ("，实际调度对象是运行在边缘节点上的", INK, F_BODY),
            (" Pod 工作负载", RED, F_BODY_B),
            ("。", INK, F_BODY),
        ],
    )
    draw_chunks(
        draw,
        54,
        171,
        [
            ("调度器可直接使用 Kubernetes 已暴露的资源与约束：", INK, F_BODY),
            ("4 类内置可计量资源", RED, F_BODY_B),
            ("、", INK, F_BODY),
            ("N 类扩展资源", RED, F_BODY_B),
            ("、", INK, F_BODY),
            ("6 类节点选择约束", RED, F_BODY_B),
            ("。", INK, F_BODY),
        ],
    )
    draw_chunks(
        draw,
        54,
        218,
        [
            ("CPU、内存、临时存储和 HugePages 可通过 requests/limits 参与调度；GPU、NPU、FPGA、NIC、摄像头等", INK, F_BODY),
            ("需要先暴露为扩展资源或设备对象", RED, F_BODY_B),
            ("。", INK, F_BODY),
        ],
    )
    draw_chunks(
        draw,
        54,
        265,
        [
            ("KubeEdge 设备管理侧还可通过", INK, F_BODY),
            (" DeviceModel、DeviceInstance、DeviceTwin、Mapper", RED, F_BODY_B),
            (" 同步外设属性、期望状态和上报状态。", INK, F_BODY),
        ],
    )
    draw.text(
        (56, 322),
        "数量口径：内置资源 4 类；节点选择约束 6 类；设备管理对象 4 类；扩展硬件资源为 N 类，取决于插件、标签或 Mapper 暴露能力。",
        font=F_SMALL_B,
        fill=INK,
    )

    panels = [
        ((32, 385, 500, 875), "KubeEdge 可调度对象"),
        ((525, 385, 1098, 875), "算力大小与资源指标"),
        ((1125, 385, 1568, 875), "调度约束与扩展设备"),
    ]
    for box, title in panels:
        x1, y1, x2, y2 = box
        rounded(draw, box, PANEL, "#D5E2E2", radius=0, width=1)
        draw.rectangle((x1, y1, x2, y1 + 46), fill=DARK_TEAL)
        center_text(draw, (x1, y1, x2, y1 + 46), title, F_CARD_TITLE, "#FFFFFF")

    # Left panel
    draw.text((58, 454), "框架对象", font=F_SMALL_B, fill=MUTED)
    draw.text((58, 482), "4", font=F_NUM, fill=RED)
    draw.text((118, 500), "类可调度/管理对象", font=F_CARD_TITLE, fill=INK)
    object_card(draw, 58, 542, 390, 74, "Edge Node", "边端节点，承载 Pod 运行", BLUE, "NODE")
    object_card(draw, 58, 626, 390, 74, "Pod / Workload", "Deployment、Job 等最终落到 Pod", TEAL, "POD")
    object_card(draw, 58, 710, 390, 74, "Device CRD", "DeviceModel / Instance / Twin", AMBER, "DEV")
    object_card(draw, 58, 794, 390, 74, "Extended Resource", "GPU/NPU/FPGA/NIC 等整数资源", PURPLE, "EXT")

    # Middle panel
    draw.text((555, 454), "资源口径：4 类内置 + N 类扩展/节点量", font=F_SMALL_B, fill=MUTED)
    metric_card(draw, 555, 492, 250, 92, "CPU 算力", "cpu，core/mCPU", TEAL, "CPU")
    metric_card(draw, 827, 492, 250, 92, "内存容量", "memory，单位 bytes", BLUE, "MEM")
    metric_card(draw, 555, 604, 250, 92, "临时存储", "ephemeral-storage", GREEN, "DISK")
    metric_card(draw, 827, 604, 250, 92, "HugePages", "hugepages-<size>", AMBER, "HP")
    metric_card(draw, 555, 716, 250, 92, "扩展资源", "GPU/NPU 等", PURPLE, "EXT")
    metric_card(draw, 827, 716, 250, 92, "节点资源量", "capacity / alloc.", RED, "CAP")
    rounded(draw, (555, 828, 1077, 858), "#FFFFFF", TEAL, radius=8, width=1)
    center_text(draw, (555, 828, 1077, 858), "Pod 按 requests/limits 申请资源；扩展资源一般按整数数量申请", F_TINY, TEAL)

    # Right panel
    draw.text((1152, 454), "6", font=F_NUM, fill=RED)
    draw.text((1210, 472), "类常用节点选择约束", font=F_CARD_TITLE, fill=INK)
    draw.text((1152, 512), "用于决定 Pod 可以落到哪些边缘节点：", font=F_SMALL, fill=MUTED)
    constraints = [
        ("nodeName", "指定节点", SOFT_TEAL, TEAL),
        ("nodeSelector", "标签选择", SOFT_BLUE, BLUE),
        ("nodeAffinity", "节点亲和", SOFT_GREEN, GREEN),
        ("Pod亲和/反亲和", "协同或隔离部署", SOFT_AMBER, AMBER),
        ("taints/tolerations", "污点与容忍", SOFT_RED, RED),
        ("topology spread", "拓扑分散", "#F4ECFF", PURPLE),
    ]
    positions = [
        (1152, 548),
        (1352, 548),
        (1152, 633),
        (1352, 633),
        (1152, 718),
        (1352, 718),
    ]
    for (title, body, fill, color), (px, py) in zip(constraints, positions):
        constraint_card(draw, px, py, 186, 74, title, body, fill, color)

    rounded(draw, (1152, 838, 1538, 864), "#FFFFFF", TEAL, radius=8, width=1)
    center_text(draw, (1152, 838, 1538, 864), "扩展硬件：通过 Device Plugin / Mapper / 标签暴露后参与调度", F_TINY, TEAL)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT)
    img.save(LEGACY_PNG_OUT)


def main() -> None:
    draw_slide()
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {LEGACY_PNG_OUT}")


if __name__ == "__main__":
    main()
