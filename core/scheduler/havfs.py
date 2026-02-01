import math
from dataclasses import dataclass

class HoltLinearPredictor:
    """
    双指数平滑预测器 (Holt's Linear Trend)
    能够同时捕捉数据的 Level (基线) 和 Trend (趋势)
    """
    def __init__(self, alpha=0.5, beta=0.3):
        self.alpha = alpha  # Level 平滑系数 (0-1)
        self.beta = beta    # Trend 平滑系数 (0-1)
        self.level = None
        self.trend = None
        
    def update(self, x_actual: float) -> float:
        """更新模型并返回对下一时刻的预测值"""
        # 初始化
        if self.level is None:
            self.level = x_actual
            self.trend = 0.0
            return x_actual
        
        # 1. 保存旧的 Level 用于计算 Trend
        last_level = self.level
        
        # 2. 更新 Level (当前观测值与模型预测值的加权)
        # L_t = alpha * x_t + (1 - alpha) * (L_{t-1} + T_{t-1})
        self.level = self.alpha * x_actual + (1 - self.alpha) * (self.level + self.trend)
        
        # 3. 更新 Trend (当前趋势与历史趋势的加权)
        # T_t = beta * (L_t - L_{t-1}) + (1 - beta) * T_{t-1}
        self.trend = self.beta * (self.level - last_level) + (1 - self.beta) * self.trend
        
        # 4. 预测下一时刻: y_hat_{t+1} = L_t + T_t
        return self.level + self.trend

class HAVFS:
    """
    HAVFS v2.0: 基于预测误差的 AIMD 自适应变频算法
    Prediction-Error Driven Sampling with AIMD Control
    """
    def __init__(self, t_min=0.5, t_max=5.0, error_threshold=5.0):
        self.t_min = t_min
        self.t_max = t_max
        self.threshold = error_threshold # 容忍的预测误差阈值(例如 5% 利用率偏差)
        
        # 核心组件：双指数平滑预测器
        self.predictor = HoltLinearPredictor(alpha=0.6, beta=0.3)
        
        # 状态变量
        self.current_interval = 1.0
        self.predicted_next = None

    def update(self, metrics) -> tuple:
        """
        输入: 当前指标 metrics
        输出: (next_interval, risk_score, state_label)
        """
        # 以利用率作为主要观测对象 (也可改为多维加权)
        x_actual = metrics.utilization
        
        # --- 步骤 1: 计算预测误差 (Information Value) ---
        # 误差代表了“不确定性”或“风险”
        if self.predicted_next is None:
            error = 0.0
        else:
            error = abs(x_actual - self.predicted_next)
        
        # --- 步骤 2: 更新预测模型 ---
        self.predicted_next = self.predictor.update(x_actual)
        
        # --- 步骤 3: AIMD 动态控制 (核心算法) ---
        # 逻辑: 误差越大，说明当前采样频率丢失了信息，必须加密采样
        
        state_label = "STABLE"
        
        if error > self.threshold:
            # [Multiplicative Decrease] 乘性减 -> 缩短间隔，提升频率
            # 应对突发流量，指数级响应
            
            scale_factor = 0.5  # 默认减半
            if error > self.threshold * 3:
                scale_factor = 0.25 # 严重误差，急剧提升频率
            
            self.current_interval = self.current_interval * scale_factor
            
            # 边界保护
            if self.current_interval < self.t_min:
                self.current_interval = self.t_min
                
            state_label = "ADAPT_HIGH"
            
        else:
            # [Additive Increase] 加性增 -> 延长间隔，降低频率
            # 误差在容忍范围内，线性放松采样，节省系统开销
            
            self.current_interval = self.current_interval + 0.2
            
            # 边界保护
            if self.current_interval > self.t_max:
                self.current_interval = self.t_max
                
            state_label = "ADAPT_LOW"

        # 返回: 间隔, 风险值(此处用预测误差代替risk), 状态
        return self.current_interval, error, state_label