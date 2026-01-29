from core.risk.baseline import OnlineEMA
from core.risk.risk_score import RiskAnalyzer


class HAVFS:
    """
    Algorithm 1: HAVFS Adaptive Sampling
    输入：metrics(t)
    输出：interval(t), risk(t), state
    """

    def __init__(self, t_min=0.5, t_max=5.0):

        self.t_min = t_min
        self.t_max = t_max

        # Step1: 在线基线
        self.ema = OnlineEMA(alpha=0.3)

        # Step2: 风险分析器
        self.risk_analyzer = RiskAnalyzer(window_size=5)

        # Step5: 滞回状态机
        self.state = "LOW"
        self.th_high = 1.5
        self.th_low = 0.8

    def risk_to_interval(self, risk):
        risk = min(max(risk, 0.0), 3.0)
        ratio = risk / 3.0
        return self.t_max - ratio * (self.t_max - self.t_min)

    def update(self, metrics):

        # 当前利用率
        x = metrics.utilization

        # Step1 EMA趋势预测
        baseline = self.ema.update(x)

        # Step2-3 风险计算与融合
        risk = self.risk_analyzer.compute(x, baseline)

        # Step4 风险→频率映射
        interval = self.risk_to_interval(risk)

        # Step5 滞回控制
        if risk > self.th_high:
            self.state = "HIGH"
        elif risk < self.th_low:
            self.state = "LOW"

        return interval, risk, self.state
