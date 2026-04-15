"""PerfMon API collector for CUCM performance counters."""

import logging
import re
import xml.etree.ElementTree as ET

from prometheus_client.core import GaugeMetricFamily

from cucm_exporter.constants import NS, PERFMON_COLLECT_BODY, PERFMON_PATH
from cucm_exporter.metric_naming import to_prometheus_name

logger = logging.getLogger(__name__)

# Regex to parse counter name: \\host\Object\Counter or \\host\Object(Instance)\Counter
COUNTER_NAME_RE = re.compile(
    r"^\\\\[^\\]+\\([^\\]+?)(?:\(([^)]+)\))?\\(.+)$"
)


class PerfMonCollector:
    """Collects PerfMon counters via perfmonCollectCounterData."""

    def __init__(self, config, soap_client, server_config):
        self.config = config
        self.client = soap_client
        self.server = server_config
        self.objects = config.perfmon_objects

    def collect(self):
        """Yield GaugeMetricFamily for each PerfMon object."""
        for obj_name in self.objects:
            try:
                raw_xml = self._fetch_object(obj_name)
                counters = self._parse_response(raw_xml)
                yield from self._to_metrics(obj_name, counters)
            except Exception as e:
                logger.warning(
                    "[%s] Failed to collect PerfMon object '%s': %s",
                    self.server.name,
                    obj_name,
                    e,
                )

    def _fetch_object(self, object_name: str) -> str:
        """Call perfmonCollectCounterData for a given object."""
        body = PERFMON_COLLECT_BODY.format(
            host=self.server.host, object_name=object_name
        )
        return self.client.send(
            path=PERFMON_PATH,
            soap_action="perfmonCollectCounterData",
            body_xml=body,
        )

    def _parse_response(self, xml_text: str) -> list:
        """Parse SOAP response into list of counter dicts.

        Each dict has keys: object, instance (or None), counter, value
        """
        root = ET.fromstring(xml_text)
        items = root.findall(".//ns1:perfmonCollectCounterDataReturn", NS)

        counters = []
        for item in items:
            name_elem = item.find("ns1:Name", NS)
            value_elem = item.find("ns1:Value", NS)
            cstatus_elem = item.find("ns1:CStatus", NS)

            if name_elem is None or value_elem is None or cstatus_elem is None:
                continue

            # Only accept CStatus 0 or 1 (valid values)
            try:
                cstatus = int(cstatus_elem.text)
            except (ValueError, TypeError):
                continue

            if cstatus not in (0, 1):
                logger.debug(
                    "Skipping counter %s with CStatus=%d",
                    name_elem.text,
                    cstatus,
                )
                continue

            try:
                value = int(value_elem.text)
            except (ValueError, TypeError):
                logger.debug(
                    "Skipping counter %s with non-integer value: %s",
                    name_elem.text,
                    value_elem.text,
                )
                continue

            match = COUNTER_NAME_RE.match(name_elem.text)
            if not match:
                logger.debug(
                    "Could not parse counter name: %s", name_elem.text
                )
                continue

            obj_name, instance, counter_name = match.groups()
            counters.append(
                {
                    "object": obj_name,
                    "instance": instance,
                    "counter": counter_name,
                    "value": value,
                }
            )

        return counters

    def _to_metrics(self, object_name, counters):
        """Convert parsed counters to Prometheus GaugeMetricFamily objects."""
        server_name = self.server.name
        # Group counters by counter name
        grouped = {}
        for c in counters:
            key = c["counter"]
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(c)

        for counter_name, entries in grouped.items():
            prom_name = to_prometheus_name(object_name, counter_name)

            has_instances = any(e["instance"] is not None for e in entries)

            if has_instances:
                gauge = GaugeMetricFamily(
                    prom_name,
                    f"CUCM {object_name} {counter_name}",
                    labels=["cucm_host", "instance"],
                )
                for entry in entries:
                    instance = entry["instance"] or "default"
                    gauge.add_metric([server_name, instance], entry["value"])
            else:
                gauge = GaugeMetricFamily(
                    prom_name,
                    f"CUCM {object_name} {counter_name}",
                    labels=["cucm_host"],
                )
                gauge.add_metric([server_name], entries[0]["value"])

            yield gauge
