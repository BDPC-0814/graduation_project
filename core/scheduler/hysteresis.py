# core/scheduler/hysteresis.py

class HysteresisFSM:
    """
    滞回控制状态机：
    防止采样频率频繁抖动
    """

    def __init__(self, r_high=1.5, r_low=0.8):
        self.r_high = r_high
        self.r_low = r_low
        self.state = "LOW"

    def update(self, risk):
        if self.state == "LOW" and risk > self.r_high:
            self.state = "HIGH"
        elif self.state == "HIGH" and risk < self.r_low:
            self.state = "LOW"
        return self.state
