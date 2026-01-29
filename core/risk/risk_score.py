# import numpy as np


# def anomaly_risk(value, mean, std):
#     return abs(value - mean) / (std + 1e-6)


# def burst_risk(delta):
#     return abs(delta)


# def pressure_risk(value, threshold=80):
#     return max(0.0, value - threshold) / 20.0


# def drift_risk(mean_now, mean_prev):
#     return abs(mean_now - mean_prev)


# def fused_risk(risks, weights=None):
#     if weights is None:
#         weights = [1.0] * len(risks)
#     return sum(r * w for r, w in zip(risks, weights)) / sum(weights)

# core/risk/risk_score.py

# class RiskEvaluator:
#     def anomaly_risk(self, current, baseline):
#         return abs(current - baseline) / max(baseline, 1.0)

#     def pressure_risk(self, current, threshold=80.0):
#         return max(0.0, current - threshold) / 20.0

#     def burst_risk(self, current, baseline):
#         return abs(current - baseline) / 50.0

#     def drift_risk(self, current, baseline):
#         return abs(current - baseline) / 100.0

#     def compute(self, current, baseline):
#         r1 = self.anomaly_risk(current, baseline)
#         r2 = self.pressure_risk(current)
#         r3 = self.burst_risk(current, baseline)
#         r4 = self.drift_risk(current, baseline)

#         return r1 + r2 + r3 + r4

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
