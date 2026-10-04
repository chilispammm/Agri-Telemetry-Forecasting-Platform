"""
UI Package for Agri Telemetry & Forecasting Platform.
Provides minimal, zero-dependency operational cockpit server and API adapters.
"""

from agri_telemetry.ui.server import DashboardServer, run_dashboard_server

__all__ = ["DashboardServer", "run_dashboard_server"]
