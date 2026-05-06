"""OpenTelemetry custom metrics for Upload Web (#117).

Emits counters and histograms for upload sessions, files, SAS tokens,
preflight/confirm latency, abandonment, and errors.  Metrics are exported
to Application Insights via the OTLP or Azure Monitor exporter when
``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from opentelemetry import metrics
from opentelemetry.metrics import Meter

logger = logging.getLogger(__name__)

_METER_NAME = "verdecora.upload_web"
_METER_VERSION = "1.0.0"

_meter: Meter = metrics.get_meter(_METER_NAME, _METER_VERSION)

# ── Counters ────────────────────────────────────────────────────────────

upload_sessions_created = _meter.create_counter(
    name="upload_sessions_created",
    description="Total upload sessions created",
    unit="{session}",
)

upload_files_processed = _meter.create_counter(
    name="upload_files_processed",
    description="Files registered in upload sessions",
    unit="{file}",
)

upload_sas_generated = _meter.create_counter(
    name="upload_sas_generated",
    description="SAS URLs generated for blob uploads",
    unit="{token}",
)

upload_session_abandoned = _meter.create_counter(
    name="upload_session_abandoned",
    description="Sessions started but never confirmed",
    unit="{session}",
)

upload_errors = _meter.create_counter(
    name="upload_errors",
    description="Errors during upload operations",
    unit="{error}",
)

# ── Histograms ──────────────────────────────────────────────────────────

upload_preflight_duration_seconds = _meter.create_histogram(
    name="upload_preflight_duration_seconds",
    description="Duration of preflight checks",
    unit="s",
)

upload_confirm_duration_seconds = _meter.create_histogram(
    name="upload_confirm_duration_seconds",
    description="Duration of session confirmation",
    unit="s",
)


# ── Helpers ─────────────────────────────────────────────────────────────


def record_session_created() -> None:
    upload_sessions_created.add(1)


def record_file_processed(supplier: str = "unknown") -> None:
    upload_files_processed.add(1, {"supplier": supplier})


def record_sas_generated() -> None:
    upload_sas_generated.add(1)


def record_session_abandoned() -> None:
    upload_session_abandoned.add(1)


def record_error(error_type: str) -> None:
    upload_errors.add(1, {"error_type": error_type})


@contextmanager
def measure_preflight() -> Generator[None, None, None]:
    start = time.monotonic()
    try:
        yield
    finally:
        upload_preflight_duration_seconds.record(time.monotonic() - start)


@contextmanager
def measure_confirm() -> Generator[None, None, None]:
    start = time.monotonic()
    try:
        yield
    finally:
        upload_confirm_duration_seconds.record(time.monotonic() - start)


def configure_telemetry(connection_string: str) -> None:
    """Bootstrap the Azure Monitor OTel exporter if a connection string is available."""
    if not connection_string:
        logger.info("No APPLICATIONINSIGHTS_CONNECTION_STRING set; OTel metrics are local only.")
        return

    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        exporter = AzureMonitorMetricExporter(connection_string=connection_string)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)
        logger.info("Azure Monitor metrics exporter configured for Upload Web.")
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry-exporter not installed; metrics will not be exported to Application Insights."
        )
    except Exception:
        logger.exception("Failed to configure Azure Monitor metrics exporter.")
