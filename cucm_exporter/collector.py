"""Top-level CUCM collector that orchestrates PerfMon and RISPort sub-collectors."""

import logging
import time

from prometheus_client.core import GaugeMetricFamily

from cucm_exporter.perfmon_collector import PerfMonCollector
from cucm_exporter.risport_collector import RISPortCollector
from cucm_exporter.soap_client import SOAPClient

logger = logging.getLogger(__name__)


class CUCMCollector:
    """Custom Prometheus collector for CUCM.

    Registered with prometheus_client.REGISTRY. On each /metrics scrape,
    the collect() method queries all configured CUCM servers and yields
    metric families with a cucm_host label for server identification.
    """

    def __init__(self, config, server_entries):
        """Initialize with a list of (server_config, soap_client) tuples."""
        self.config = config
        self.server_entries = []

        for server_config, soap_client in server_entries:
            perfmon = (
                PerfMonCollector(config, soap_client, server_config)
                if config.perfmon_enabled
                else None
            )
            risport = (
                RISPortCollector(config, soap_client, server_config)
                if config.risport_enabled
                else None
            )
            self.server_entries.append(
                (server_config, perfmon, risport)
            )

    def collect(self):
        """Yield all metric families. Called by prometheus_client on each scrape."""
        total_start = time.monotonic()

        up_gauge = GaugeMetricFamily(
            "cucm_up",
            "Whether the exporter can reach the CUCM server (1=up, 0=down)",
            labels=["cucm_host"],
        )
        duration_gauge = GaugeMetricFamily(
            "cucm_scrape_duration_seconds",
            "Time taken to collect metrics from a CUCM server",
            labels=["cucm_host"],
        )

        for server_config, perfmon, risport in self.server_entries:
            server_start = time.monotonic()
            server_up = 1

            try:
                if perfmon:
                    for metric in perfmon.collect():
                        yield metric

                if risport:
                    for metric in risport.collect():
                        yield metric
            except Exception as e:
                logger.error(
                    "[%s] Collection failed: %s", server_config.name, e
                )
                server_up = 0

            server_duration = time.monotonic() - server_start
            up_gauge.add_metric([server_config.name], server_up)
            duration_gauge.add_metric([server_config.name], server_duration)

            logger.info(
                "[%s] Scrape completed in %.2fs",
                server_config.name,
                server_duration,
            )

        yield up_gauge
        yield duration_gauge

        total_duration = time.monotonic() - total_start
        logger.info(
            "Total scrape completed in %.2fs (%d servers)",
            total_duration,
            len(self.server_entries),
        )
