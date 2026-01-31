import numpy as np


class RiskAnalyzer:
    """
    多维风险计算：
    anomaly + jump + stress + drift
    """

    def __init__(self, window_size=5):
        self.window_size = window_size
        self.history = []

    def compute(self, x, baseline):

        self.history.append(x)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        # 1. 异常风险
        r_anom = abs(x - baseline)

        # 2. 突变风险 Δx
        r_jump = abs(x - self.history[-2]) if len(self.history) > 1 else 0

        # 3. 压力风险
        r_stress = x / 100.0

        # 4. 漂移风险 Var(window)
        r_drift = np.var(self.history) if len(self.history) >= 2 else 0

        # 总风险融合
        risk = 0.4 * r_anom + 0.3 * r_jump + 0.2 * r_stress + 0.1 * r_drift
        return risk
