from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "figures"


def configure_chinese_font():
    candidates = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Zen Hei",
        "Arial Unicode MS",
    ]
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            break
    else:
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


PALETTE = {
    "blue": ("#f7fbff", "#7aa6d8"),
    "cyan": ("#f5fbfc", "#78b9c3"),
    "amber": ("#fffaf1", "#cfb073"),
    "rose": ("#fff7f6", "#cc8a83"),
    "indigo": ("#f7f7ff", "#8c92d8"),
    "green": ("#f6fbf7", "#84b68c"),
    "slate": ("#f8fafc", "#94a3b8"),
}


def add_box(
    ax,
    x,
    y,
    w,
    h,
    title,
    lines,
    color_key="blue",
    title_size=14,
    body_size=11,
    header_ratio=0.30,
    header_min=0.055,
    body_linespacing=1.30,
):
    facecolor, edgecolor = PALETTE[color_key]
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.6,
        edgecolor=edgecolor,
        facecolor=facecolor,
    )
    ax.add_patch(patch)

    header_h = max(h * header_ratio, header_min)
    title_y = y + h - 0.016
    body_top_y = y + h - header_h - 0.012

    ax.plot(
        [x + 0.02, x + w - 0.02],
        [y + h - header_h, y + h - header_h],
        color=edgecolor,
        linewidth=0.9,
        alpha=0.35,
    )
    ax.text(
        x + w / 2,
        title_y,
        title,
        ha="center",
        va="top",
        fontsize=title_size,
        weight="bold",
        color="#0f172a",
    )
    ax.text(
        x + w / 2,
        body_top_y,
        "\n".join(lines),
        ha="center",
        va="top",
        fontsize=body_size,
        color="#334155",
        linespacing=body_linespacing,
    )


def add_arrow(ax, start, end, text=None, color="#64748b", lw=2.0, text_size=12):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=15,
        linewidth=lw,
        color=color,
        connectionstyle="arc3,rad=0.0",
    )
    ax.add_patch(arrow)
    if text:
        tx = (start[0] + end[0]) / 2
        ty = (start[1] + end[1]) / 2
        ax.text(
            tx,
            ty + 0.014,
            text,
            ha="center",
            va="bottom",
            fontsize=text_size,
            color=color,
        )


def save_figure(fig, name):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)
    return path


def draw_architecture():
    fig, ax = plt.subplots(figsize=(18, 9.5))
    fig.patch.set_facecolor("#ffffff")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    boxes = [
        (0.08, 0.72, "第一层 设备接入层", ["BaseAdapter", "CPU / GPU / NPU 三类适配器", "屏蔽不同硬件与厂商接口差异"], "blue"),
        (0.54, 0.72, "第二层 统一采样层", ["DeviceSampler", "fast path / slow path", "采样阶段内嵌变频控制"], "cyan"),
        (0.54, 0.47, "第三层 调度与决策层", ["HAVFS 算法", "依据实时风险动态调整采样间隔", "运行时取最小采样间隔", "UnifiedScheduler 已实现待整合"], "amber"),
        (0.08, 0.47, "第四层 边端运行时与传输层", ["EdgeAgent / RingBuffer", "SQLiteOutbox / HTTPUploader", "解耦采集与上送，支持重试"], "rose"),
        (0.08, 0.22, "第五层 平台服务层", ["FastAPI + SQLite + DatabaseService", "负责接收、存储与查询", "内部已实现规则判断与告警流转"], "indigo"),
        (0.54, 0.22, "第六层 展示与分析层", ["前端页面、ECharts、日志面板", "Prometheus / Grafana 通路", "面向可视化展示与实验分析"], "green"),
    ]

    box_w = 0.36
    box_h = 0.16
    for x, y, title, lines, color in boxes:
        add_box(
            ax,
            x,
            y,
            box_w,
            box_h,
            title,
            lines,
            color_key=color,
            title_size=15,
            body_size=10.8,
            header_ratio=0.30,
            header_min=0.055,
            body_linespacing=1.22,
        )

    add_arrow(ax, (0.44, 0.80), (0.54, 0.80))
    add_arrow(ax, (0.72, 0.72), (0.72, 0.63))
    add_arrow(ax, (0.54, 0.55), (0.44, 0.55))
    add_arrow(ax, (0.26, 0.47), (0.26, 0.38))
    add_arrow(ax, (0.44, 0.30), (0.54, 0.30))

    return save_figure(fig, "midterm_system_architecture_cn.png")


def draw_data_pipeline():
    fig, ax = plt.subplots(figsize=(19, 10))
    fig.patch.set_facecolor("#ffffff")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Top main path
    add_box(ax, 0.04, 0.74, 0.18, 0.14, "设备适配层", ["CPU / GPU / NPU 适配器", "输出 fast / slow 字段"], color_key="blue", body_size=10.8)
    add_box(ax, 0.28, 0.74, 0.18, 0.14, "统一采样层", ["DeviceSampler", "先采 fast，再决定 slow"], color_key="cyan", body_size=10.8)
    add_box(ax, 0.52, 0.74, 0.18, 0.14, "HAVFS 决策层", ["计算风险分 R", "输出下一次采样间隔"], color_key="amber", body_size=10.8)
    add_box(ax, 0.76, 0.74, 0.18, 0.14, "运行时调度层", ["EdgeAgent 并发采样", "当前取最小采样间隔"], color_key="rose", body_size=10.8)

    add_arrow(ax, (0.22, 0.81), (0.28, 0.81))
    add_arrow(ax, (0.46, 0.81), (0.52, 0.81))
    add_arrow(ax, (0.70, 0.81), (0.76, 0.81))

    # Left validation branch: file output
    add_box(ax, 0.04, 0.47, 0.15, 0.11, "实验文件输出", ["metrics.csv", "events.csv"], color_key="slate", title_size=13, body_size=10.5, header_ratio=0.38, header_min=0.04)
    add_arrow(ax, (0.81, 0.74), (0.12, 0.58), "文件输出", text_size=13)

    # Center service chain
    add_box(ax, 0.24, 0.48, 0.16, 0.13, "内存缓冲", ["RingBuffer", "记录先入内存"], color_key="rose", body_size=10.8)
    add_box(ax, 0.43, 0.48, 0.16, 0.13, "持久化队列", ["SQLiteOutbox", "WAL 落盘与重试"], color_key="indigo", body_size=10.8)
    add_box(ax, 0.62, 0.48, 0.16, 0.13, "上传通道", ["HTTPUploader", "gzip + HTTP POST"], color_key="indigo", body_size=10.8)

    add_arrow(ax, (0.82, 0.74), (0.32, 0.61), "服务化链路", text_size=13)
    add_arrow(ax, (0.40, 0.545), (0.43, 0.545), "WAL 线程", text_size=12)
    add_arrow(ax, (0.59, 0.545), (0.62, 0.545), "上传线程", text_size=12)

    add_box(ax, 0.24, 0.22, 0.16, 0.14, "FastAPI 后端", ["/api/ingest", "解压、解析、调用入库"], color_key="green", body_size=10.8)
    add_box(ax, 0.43, 0.22, 0.18, 0.14, "数据库表", ["metrics / events / devices", "alerts / alert_rules"], color_key="green", body_size=10.8)
    add_box(ax, 0.64, 0.22, 0.16, 0.14, "前端展示", ["realtime / history / compare", "logs / events"], color_key="cyan", body_size=10.8)

    add_arrow(ax, (0.70, 0.48), (0.33, 0.36), "HTTP 上送", text_size=13)
    add_arrow(ax, (0.40, 0.29), (0.43, 0.29), "入库", text_size=12)
    add_arrow(ax, (0.61, 0.29), (0.64, 0.29), "查询", text_size=12)

    # Right validation branch: metrics monitoring
    add_box(ax, 0.80, 0.48, 0.14, 0.11, "Prometheus\nExporter", ["指标监控通路"], color_key="blue", title_size=13, body_size=10.5, header_ratio=0.42, header_min=0.04)
    add_box(ax, 0.80, 0.26, 0.14, 0.11, "Grafana", ["监控可视化"], color_key="slate", title_size=13, body_size=10.5, header_ratio=0.42, header_min=0.04)

    add_arrow(ax, (0.87, 0.74), (0.87, 0.59), "指标监控", text_size=13)
    add_arrow(ax, (0.87, 0.48), (0.87, 0.37), text_size=12)

    return save_figure(fig, "midterm_data_pipeline_cn.png")


def draw_havfs_algorithm():
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.patch.set_facecolor("#ffffff")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    add_box(ax, 0.15, 0.80, 0.70, 0.11, "输入", ["利用率、温度、功耗、历史窗口、上一时刻采样间隔"], color_key="blue", title_size=15, body_size=12, header_ratio=0.40, header_min=0.04)

    add_box(ax, 0.06, 0.56, 0.22, 0.16, "Step 1 在线预测", ["Holt 双指数平滑", "维护 level 与 trend", "预测下一时刻利用率"], color_key="cyan", body_size=11)
    add_box(ax, 0.39, 0.56, 0.22, 0.16, "Step 2 多维风险计算", ["A: max(0, x-80)", "J: |x - x_last|", "P: 滑动窗口均值", "D: |x - x_pred|"], color_key="amber", body_size=11)
    add_box(ax, 0.72, 0.56, 0.22, 0.16, "Step 3 风险融合与控制", ["风险归一化与加权求和得到 R", "映射到 target_interval", "AIMD: 风险升高乘性减小", "风险降低加性增大"], color_key="rose", body_size=10.5)
    add_box(ax, 0.56, 0.28, 0.24, 0.18, "Step 4 滞回状态机", ["enter_high / exit_high 双门限", "避免阈值附近频繁切换", "输出 LOW / HIGH 与状态标签"], color_key="indigo", body_size=11)
    add_box(ax, 0.24, 0.28, 0.24, 0.18, "Step 5 高风险缓冲", ["HIGH 状态时写入 RiskBuffer", "保留关键窗口样本", "支撑离线分析与实验复现"], color_key="green", body_size=11)

    add_box(ax, 0.20, 0.05, 0.60, 0.11, "输出", ["interval、risk_score、state_label、breakdown(A/J/P/D)"], color_key="slate", title_size=15, body_size=11.5, header_ratio=0.40, header_min=0.04)

    add_arrow(ax, (0.26, 0.64), (0.39, 0.64), text_size=12)
    add_arrow(ax, (0.61, 0.64), (0.72, 0.64), text_size=12)
    add_arrow(ax, (0.83, 0.55), (0.70, 0.47), text="R / interval", text_size=12)
    add_arrow(ax, (0.56, 0.37), (0.48, 0.37), text="HIGH 状态触发", text_size=13)
    add_arrow(ax, (0.36, 0.28), (0.44, 0.16), text_size=12)
    add_arrow(ax, (0.68, 0.28), (0.56, 0.16), text_size=12)

    return save_figure(fig, "midterm_havfs_algorithm_cn.png")


def draw_havfs_state_machine():
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.patch.set_facecolor("#ffffff")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    add_box(ax, 0.08, 0.58, 0.22, 0.18, "低频(稳定巡检)", ["默认启动状态", "风险较低", "采样间隔接近 t_max"], color_key="blue", body_size=11.5)
    add_box(ax, 0.39, 0.74, 0.22, 0.18, "高频(突发捕获)", ["R 超过 enter_high", "且 A > 0 或 J > 20", "快速缩短采样间隔"], color_key="rose", body_size=11.2)
    add_box(ax, 0.39, 0.30, 0.22, 0.18, "高频(驻留观察)", ["已处于 HIGH", "持续高压但无明显突发", "维持高频继续观察"], color_key="amber", body_size=11.2)
    add_box(ax, 0.72, 0.58, 0.20, 0.18, "低频(平滑恢复)", ["R < exit_high", "AIMD 加性增大间隔", "逐步恢复而不瞬间拉满"], color_key="green", body_size=11.0)

    add_arrow(ax, (0.30, 0.70), (0.39, 0.81), text="R > enter_high\n且 A>0 或 J>20", text_size=13)
    add_arrow(ax, (0.31, 0.60), (0.38, 0.39), text="R > enter_high\n持续压力/漂移上升", text_size=13)
    add_arrow(ax, (0.50, 0.74), (0.50, 0.48), text="\n\n突发减弱但仍处 HIGH", text_size=12)
    add_arrow(ax, (0.62, 0.81), (0.72, 0.72), text="R < exit_high", text_size=13)
    add_arrow(ax, (0.62, 0.40), (0.72, 0.62), text="R < exit_high", text_size=13)
    add_arrow(ax, (0.72, 0.65), (0.30, 0.65), text="间隔恢复接近 t_max且风险长期稳定", text_size=13)
    add_arrow(ax, (0.72, 0.76), (0.61, 0.87), text="风险再次升高", text_size=12)
    add_arrow(ax, (0.76, 0.58), (0.62, 0.33), text="持续压力再现", text_size=12)

    return save_figure(fig, "midterm_havfs_state_machine_cn.png")


def draw_todo_roadmap():
    fig, ax = plt.subplots(figsize=(18, 8.5))
    fig.patch.set_facecolor("#ffffff")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    items = [
        (0.05, "阶段一\n基础完善", ["静态元数据正式入库", "完成元数据展示"], "blue"),
        (0.29, "阶段二\n链路整合", ["UnifiedScheduler 整合", "打通主运行链路"], "cyan"),
        (0.53, "阶段三\n能力扩展", ["完善 GPU / NPU 采集", "提升覆盖范围与精度"], "amber"),
        (0.77, "阶段四\n论文收敛", ["长时序存储升级", "系统实验与参数分析"], "rose"),
    ]

    y = 0.42
    w = 0.17
    h = 0.26
    for x, title, lines, color in items:
        add_box(ax, x, y, w, h, title, lines, color_key=color, title_size=15, body_size=12, header_ratio=0.36, header_min=0.075)

    for idx in range(len(items) - 1):
        add_arrow(ax, (items[idx][0] + w, y + h / 2), (items[idx + 1][0], y + h / 2), text_size=12)

    return save_figure(fig, "midterm_todo_roadmap_cn.png")


def draw_issue_solution():
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.patch.set_facecolor("#ffffff")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    left_x = 0.05
    right_x = 0.56
    w = 0.34
    h = 0.145
    ys = [0.77, 0.58, 0.39, 0.20]

    issues = [
        ("问题 1", ["异构采集覆盖仍有限", "GPU / NPU 适配路径偏少", "多卡与拓扑支持不足"]),
        ("问题 2", ["统一调度尚未完全闭环", "UnifiedScheduler 与主链路", "仍需进一步整合"]),
        ("问题 3", ["存储方案仍偏原型", "当前以 CSV / SQLite 为主", "长时序能力不足"]),
        ("问题 4", ["实验和参数研究还不充分", "对比实验、消融实验", "与参数寻优仍待完成"]),
    ]
    solutions = [
        ("对策 1", ["扩展更多厂商接口", "补齐多设备枚举", "完善异常与健康字段"]),
        ("对策 2", ["统一 HAVFS 返回接口", "将全局调度纳入", "EdgeAgent 主循环"]),
        ("对策 3", ["短期保留 SQLite 缓冲", "长期扩展时序库存储", "提升查询与扩展能力"]),
        ("对策 4", ["建立标准实验协议", "补充对比组和消融实验", "开展参数寻优与泛化验证"]),
    ]

    for y, issue, solution in zip(ys, issues, solutions):
        add_box(ax, left_x, y, w, h, issue[0], issue[1], color_key="rose", title_size=15, body_size=11.3, header_ratio=0.34, header_min=0.065, body_linespacing=1.28)
        add_box(ax, right_x, y, w, h, solution[0], solution[1], color_key="green", title_size=15, body_size=11.3, header_ratio=0.34, header_min=0.065, body_linespacing=1.28)
        add_arrow(ax, (left_x + w, y + h / 2), (right_x, y + h / 2), text_size=12)

    return save_figure(fig, "midterm_issue_solution_cn.png")


def main():
    configure_chinese_font()
    outputs = [
        draw_architecture(),
        draw_data_pipeline(),
        draw_havfs_algorithm(),
        draw_havfs_state_machine(),
        draw_todo_roadmap(),
        draw_issue_solution(),
    ]
    print("Generated files:")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
