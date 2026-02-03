# core/scheduler/hysteresis.py

"""
[DEPRECATED] 该模块已在 HAVFS v3.0 中废弃。
滞回控制逻辑已整合至 core/scheduler/havfs.py 中的 AIMD (加性增、乘性减) 策略。
保留此文件仅为了兼容旧版本代码或作为历史参考。
"""

class HysteresisFSM:
    def __init__(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        return "LOW"