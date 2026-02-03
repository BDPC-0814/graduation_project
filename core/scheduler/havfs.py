# core/scheduler/havfs.py

import math
from collections import deque
from dataclasses import dataclass

# ==========================================================
# Step 1: 在线基线化与趋势预测 (Holt Linear)
# ==========================================================

class HoltLinearPredictor:
    """
    Holt 双指数平滑预测器
    同时学习：
    - Level (基线): 数据的长期均值水平
    - Trend (趋势): 数据的变化斜率
    """

    def __init__(self, alpha=0.6, beta=0.3):
        self.alpha = alpha
        self.beta = beta
        self.level = None
        self.trend = None

    def update(self, x_actual: float) -> float:
        """
        输入: 当前观测值 x_actual
        输出: 下一时刻预测值 x_hat
        """
        if self.level is None:
            self.level = x_actual
            self.trend = 0.0
            return x_actual

        last_level = self.level

        # Level 更新 (当前值与预测值的加权)
        self.level = (
            self.alpha * x_actual
            + (1 - self.alpha) * (self.level + self.trend)
        )

        # Trend 更新 (当前趋势与历史趋势的加权)
        self.trend = (
            self.beta * (self.level - last_level)
            + (1 - self.beta) * self.trend
        )

        # 预测下一时刻: y_hat = L + T
        return self.level + self.trend


# ==========================================================
# Step 5: 高风险窗口缓冲机制 (Exploration Buffer)
# ==========================================================

class RiskBuffer:
    """
    探索与缓冲模块:
    在 HIGH 风险阶段保存关键窗口数据, 用于后续离线分析或模型微调
    """

    def __init__(self, maxlen=20):
        self.buffer = deque(maxlen=maxlen)

    def store(self, metrics):
        self.buffer.append(metrics)

    def size(self):
        return len(self.buffer)


# ==========================================================
# HAVFS v4.0 完整五步闭环实现 (论文终极版)
# ==========================================================

class HAVFS:
    """
    HAVFS v4.0: 基于多维风险感知与混合控制的自适应采样策略
    
    核心流程 (Algorithm 1):
    Step1: 在线基线化 (Holt Predictor)
    Step2: 多维风险计算 (Anomaly/Jump/Pressure/Drift)
    Step3: 风险融合与混合控制 (Mapping + AIMD)
    Step4: 滞回状态机 (Hysteresis FSM)
    Step5: 高风险缓冲 (Buffer)
    """

    def __init__(
        self,
        t_min=0.5,
        t_max=5.0,
        static_limit=80.0,
        window_size=10
    ):
        # 采样频率上下界
        self.t_min = t_min
        self.t_max = t_max

        # 静态压力阈值 (超过此值视为绝对异常)
        self.static_limit = static_limit

        # 历史滑动窗口 (用于计算 Pressure)
        self.window = deque(maxlen=window_size)

        # Step1: 预测器
        self.predictor = HoltLinearPredictor(alpha=0.6, beta=0.3)

        # Step4: 状态机参数 (修正为 0~1 范围)
        self.state = "LOW"
        self.enter_high = 0.4   # 风险 > 0.4 进入 HIGH
        self.exit_high = 0.2    # 风险 < 0.2 回到 LOW

        # 当前采样间隔
        self.current_interval = t_max

        # Step5: 缓冲区
        self.buffer = RiskBuffer(maxlen=50)

        # 辅助变量
        self.last_x = None

    # ======================================================
    # Step 2: 四分量风险计算
    # ======================================================

    def compute_risks(self, x_actual, x_pred):
        """
        计算四个维度的风险分量 (A, J, P, D)
        """
        # 1. Anomaly (异常风险): 是否超过静态安全阈值
        # 归一化参考: 超过 80% 开始计分, 满分 100%
        # max(0, x - 80) -> range [0, 20]
        A = max(0.0, x_actual - self.static_limit)

        # 2. Jump (突变风险): 相比上一次的变化幅度
        if self.last_x is None:
            J = 0.0
        else:
            J = abs(x_actual - self.last_x)

        # 3. Pressure (压力风险): 窗口内的平均负载水平
        self.window.append(x_actual)
        P_avg = sum(self.window) / len(self.window)
        # 简单归一化: 压力风险直接与负载挂钩
        P = P_avg

        # 4. Drift (漂移风险): 预测值与真实值的偏差 (Model Uncertainty)
        D = abs(x_actual - x_pred)

        # 更新历史
        self.last_x = x_actual

        return A, J, P, D

    # ======================================================
    # Step 3: 风险融合与混合控制 (Mapping + AIMD)
    # ======================================================

    def fuse_risk(self, A, J, P, D):
        """
        加权融合并归一化到 [0, 1] 区间
        """
        # 归一化系数 (根据经验值设定，保证各分量在极端情况下贡献均衡)
        # A: max~20 -> /20
        # J: max~100 -> /50 (允许跳变超过 50% 即满分)
        # P: max~100 -> /100
        # D: max~50 -> /40
        
        nA = min(A / 20.0, 1.0)
        nJ = min(J / 50.0, 1.0)
        nP = min(P / 100.0, 1.0)
        nD = min(D / 40.0, 1.0)

        # 权重分配 (可根据论文实验调整)
        w1, w2, w3, w4 = 0.3, 0.3, 0.2, 0.2
        R = w1 * nA + w2 * nJ + w3 * nP + w4 * nD
        
        return min(max(R, 0.0), 1.0)

    def hybrid_control(self, R):
        """
        改进 3: 连续映射 + AIMD 微调
        """
        # 1. 连续映射 (Mapping): 计算理论上的“目标间隔”
        # Risk=0 -> T_max; Risk=1 -> T_min
        target_interval = self.t_max - R * (self.t_max - self.t_min)

        # 2. AIMD 动态逼近 (Control):
        # 目的: 防止 target_interval 剧烈跳变导致系统震荡
        
        if target_interval < self.current_interval:
            # [Multiplicative Decrease] 乘性减
            # 风险升高，目标间隔变小 -> 快速响应
            # 逻辑: 取 (当前的一半) 与 (目标值) 的最大值，保证下降速度够快但不过头
            self.current_interval = max(target_interval, self.current_interval * 0.5)
        else:
            # [Additive Increase] 加性增
            # 风险降低，目标间隔变大 -> 缓慢恢复
            # 逻辑: 线性增加，平滑过渡
            self.current_interval = min(target_interval, self.current_interval + 0.2)
            
        return self.current_interval

    # ======================================================
    # Step 4: 滞回状态机
    # ======================================================

    def hysteresis_control(self, R):
        """
        基于滞回曲线的状态切换，防止在阈值附近反复横跳
        """
        if self.state == "LOW" and R > self.enter_high:
            self.state = "HIGH"
        elif self.state == "HIGH" and R < self.exit_high:
            self.state = "LOW"
        return self.state

    # ======================================================
    # 主更新接口
    # ======================================================

    def update(self, metrics):
        """
        执行一次完整的 HAVFS 决策循环
        输出: (interval, risk_score, state_label)
        """
        x_actual = metrics.utilization

        # Step 1: 预测
        x_pred = self.predictor.update(x_actual)

        # Step 2: 计算多维风险
        A, J, P, D = self.compute_risks(x_actual, x_pred)

        # Step 3: 融合 & 控制
        R = self.fuse_risk(A, J, P, D)
        self.current_interval = self.hybrid_control(R)

        # Step 4: 状态机判定
        raw_state = self.hysteresis_control(R)

        # Step 5: 高风险缓冲
        if raw_state == "HIGH":
            self.buffer.store(metrics)

        # 生成用于显示的中文状态标签
        if raw_state == "HIGH":
            # 细分 HIGH 的原因 (用于 UI 显示)
            if A > 0: state_label = "高频(阈值触发)"
            elif J > 20: state_label = "高频(突变检测)"
            else: state_label = "高频(高风险区)"
        else:
            # LOW 状态
            if self.current_interval < self.t_max:
                state_label = "恢复(线性回升)"
            else:
                state_label = "稳定(低频基准)"

        return self.current_interval, R * 100.0, state_label