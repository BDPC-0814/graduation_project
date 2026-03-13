# core/reporter/__init__.py

from .console_reporter import ConsoleReporter

try:
    from .prometheus_reporter import PrometheusReporter
except ModuleNotFoundError:  # Optional dependency: prometheus_client
    PrometheusReporter = None
