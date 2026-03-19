# HAVFS 实验评估报告

Generated at: 2026-03-19T22:01:35

## 1. 实验总览

| 指标 | 固定频率 | HAVFS | 说明 |
| --- | ---: | ---: | --- |
| 采样点数量 | 10 | 4 | HAVFS 采样点减少 60.00% |
| 冗余率 | 0.00% | 0.00% | 双层判定：|delta util| <= 1.0 且 delta time <= 5.0 s |
| 平均采样间隔 | 1.0 s | 4.8338 s | 已包含有效采样间隔填充 |
| 延迟 P50 | 4.93 s | 4.848205415000001 s | 事件驱动延迟 |
| 延迟 P95 | 9.159999999999997 s | 4.881140541500001 s | 无显式加速时回退到 next_refresh / interval estimate |
| CPU 平均开销 | 5.04 % | 0.125 % | |
| 内存平均开销 | 29.557 MB | 28.8486 MB | |

## 2. 指标定义

- Latency: from a significant workload event to the first accelerated response. A significant event is detected when utilization jump >= 5.0 or utilization >= the 85% quantile threshold.
- Acceleration response: interval shrinks by at least 15%, or the sampler enters a high-priority state.
- NaN avoidance: if no explicit acceleration is observed in the reaction window, latency falls back to `next_refresh`; if the trace ends, it falls back to `estimated_by_interval`.
- Redundancy: a point is redundant only when both numeric similarity and time-window similarity hold at the same time.

延迟阈值：

- 固定频率高负载阈值：13.3
- HAVFS 高负载阈值：12.8

## 3. 图表

### 3.1 利用率-时间曲线

![utilization_time](figures/utilization_time.png)

### 3.2 采样间隔-时间曲线

![interval_time](figures/interval_time.png)

### 3.3 延迟 CDF 曲线

![latency_cdf](figures/latency_cdf.png)

### 3.4 延迟箱线图

![latency_boxplot](figures/latency_boxplot.png)

## 4. 结构化输出

- 汇总 CSV：`summary_metrics.csv`
- 时序 CSV：`timeseries_metrics.csv`
- 延迟样本 CSV：`latency_samples.csv`
- JSON 报告：`report.json`
