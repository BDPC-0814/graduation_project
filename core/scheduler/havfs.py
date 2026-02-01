# core/scheduler/havfs.py

import time
import numpy as np

from core.model.base_xpu import XPUDynamicMetrics
from core.scheduler.hysteresis import HysteresisFSM


class HAVFS:
    """
    HAVFS 自适应变频采样调度器
    - 在线基线化
    - 滑动窗口检测
    - EMA趋势预测
    - 多维风险融合
    - 滞回状态机控制
    """

    def __init__(
        self,
        t_min=0.5,
        t_max=5.0,
        window_size=5,
        alpha=0.3,
        r_high=1.5,
        r_low=0.8
    ):
        self.t_min = t_min
        self.t_max = t_max
        self.window_size = window_size

        # EMA预测参数
        self.alpha = alpha
        self.pred = None

        # 滑动窗口
        self.window = []

        # 滞回状态机
        self.fsm = HysteresisFSM(r_high, r_low)

        # 上一次均值（漂移检测）
        self.last_mean = None

    # ---------------------------------------------------
    # 风险映射：Risk → Interval
    # ---------------------------------------------------
    def risk_to_interval(self, risk):
        risk = min(max(risk, 0.0), 3.0)
        ratio = risk / 3.0
        return self.t_max - ratio * (self.t_max - self.t_min)

    # ---------------------------------------------------
    # EMA预测：x_hat = αx + (1-α)x_hat_prev
    # ---------------------------------------------------
    def ema_predict(self, x):
        if self.pred is None:
            self.pred = x
        else:
            self.pred = self.alpha * x + (1 - self.alpha) * self.pred
        return self.pred

    # ---------------------------------------------------
    # 多维风险计算
    # ---------------------------------------------------
    def compute_risk(self, x):
        # 更新窗口
        self.window.append(x)
        if len(self.window) > self.window_size:
            self.window.pop(0)

        arr = np.array(self.window)

        # 在线基线统计
        mu = np.mean(arr)
        sigma = np.std(arr) + 1e-6

        # 1）异常风险
        r_anom = abs(x - mu) / sigma

        # 2）突变风险 Δx
        if len(arr) >= 2:
            dx = abs(arr[-1] - arr[-2])
        else:
            dx = 0
        r_burst = dx / 50.0

        # 3）压力风险
        r_press = x / 100.0

        # 4）漂移风险
        if self.last_mean is None:
            r_drift = 0
        else:
            r_drift = abs(mu - self.last_mean) / 100.0
        self.last_mean = mu

        # EMA趋势预测
        x_hat = self.ema_predict(x)
        r_trend = max(0, (x_hat - x) / 100.0)

        # 风险融合
        risk = (
            0.4 * r_anom +
            0.3 * r_burst +
            0.2 * r_press +
            0.1 * r_drift +
            0.2 * r_trend
        )

        return risk

    # ---------------------------------------------------
    # 主更新接口
    # ---------------------------------------------------
    def update(self, metrics: XPUDynamicMetrics):
        x = metrics.utilization

        # Step1: 风险计算
        risk = self.compute_risk(x)

        # Step2: 滞回状态更新
        state = self.fsm.update(risk)

        # Step3: 风险映射采样间隔
        interval = self.risk_to_interval(risk)

        return interval, risk, state
