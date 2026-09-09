"""Passive local hardware-report generation."""

from .bundle import render_human_report, write_support_bundle
from .collector import collect_hardware_report
from .models import ReportSnapshot

__all__ = ["ReportSnapshot", "collect_hardware_report", "render_human_report", "write_support_bundle"]
