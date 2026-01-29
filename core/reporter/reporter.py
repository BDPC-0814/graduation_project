class Reporter:
    """
    上报模块占位：
    后续可扩展 Prometheus Pushgateway / TSDB写入
    """

    def send(self, metrics, risk, interval):
        print(
            f"[REPORT] {metrics.device_id} "
            f"util={metrics.utilization:.1f}% "
            f"risk={risk:.2f} "
            f"interval={interval:.2f}s"
        )
