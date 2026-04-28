# 故障演化采样实验评估报告

Generated at: 2026-04-26T15:38:18

## 1. 实验总览

| 指标 | 固定频率 | 故障演化采样 | 说明 |
| --- | ---: | ---: | --- |
| 采样点数量 | 66 | 65 | 故障演化采样采样点减少 1.52% |
| 冗余率 | 34.85% | 16.92% | 低信息量重复采样：变化增益低、相位未变、策略未变、且处于短间隔快线重复采样 |
| 平均采样间隔 | 5.0085 s | 5.2692 s | 已包含有效采样间隔补全 |
| 延迟 P50 | 2.1710000000000065 s | 2.218999999999994 s | 事件驱动响应延迟 |
| 延迟 P95 | 3.8841000000000014 s | 3.638099999999998 s | 无显式加速时回退到 next_refresh / interval estimate |
| 慢线激活率 | 22.7273 % | 23.0769 % | 字段分层补采活跃程度 |
| 缓冲上传占比 | 0.0 % | 55.3846 % | 边端可靠执行链路参与程度 |
| CPU 平均开销 | 0.0409 % | 0.48 % | |
| 内存平均开销 | 66.5459 MB | 66.2892 MB | |

## 2. 指标定义

- Latency: measured from shared ground-truth event timestamps to the first accelerated response or first observation after the event.
- Acceleration response: interval shrinks by at least 15%, or the sampler enters a focus / recovery phase.
- NaN avoidance: if no explicit acceleration is observed in the reaction window, latency falls back to `next_refresh`; if the trace ends, it falls back to `estimated_by_interval`.
- Redundancy: a point is counted as redundant only when information gain stays low, the phase and field policy do not change, and the point appears as a short-gap fast-lane repeat sample.

延迟阈值：

- Fixed mode latency source: ground_truth_events (events=7)
- Evolution mode latency source: ground_truth_events (events=7)

## 3. 图表

### 3.1 利用率时间曲线

![utilization_time](figures/utilization_time.png)

### 3.2 采样间隔时间曲线

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
