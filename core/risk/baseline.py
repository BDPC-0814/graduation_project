class OnlineEMA:
    """
    趋势预测：EMA平滑基线
    x_hat(t) = αx(t) + (1-α)x_hat(t-1)
    """

    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.baseline = None

    def update(self, x: float) -> float:
        if self.baseline is None:
            self.baseline = x
        else:
            self.baseline = self.alpha * x + (1 - self.alpha) * self.baseline
        return self.baseline
