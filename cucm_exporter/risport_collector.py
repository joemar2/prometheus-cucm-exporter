"""RISPort70 API collector for CUCM device registration data."""

import logging
import xml.etree.ElementTree as ET
from collections import defaultdict

from prometheus_client.core import GaugeMetricFamily

from cucm_exporter.constants import RISPORT_SELECT_CM_DEVICE_BODY, RISPORT_PATH

logger = logging.getLogger(__name__)


class RISPortCollector:
    """Collects device registration data via RISPort70 selectCmDevice."""

    def __init__(self, config, soap_client, server_config):
        self.config = config
        self.client = soap_client
        self.server = server_config

    def collect(self):
        """Yield device registration metrics."""
        try:
            raw_xml = self._fetch_devices()
            devices = self._parse_response(raw_xml)
            yield from self._to_metrics(devices)
        except Exception as e:
            logger.warning(
                "[%s] Failed to collect RISPort data: %s",
                self.server.name,
                e,
            )

    def _fetch_devices(self) -> str:
        """Call selectCmDevice to get all devices."""
        body = RISPORT_SELECT_CM_DEVICE_BODY.format(
            max_devices=self.config.risport_max_devices
        )
        return self.client.send(
            path=RISPORT_PATH,
            soap_action="selectCmDevice",
            body_xml=body,
        )

    def _parse_response(self, xml_text: str) -> list:
        """Parse selectCmDevice response into a list of device dicts."""
        root = ET.fromstring(xml_text)

        # Extract TotalDevicesFound
        total_elem = root.find(".//{http://schemas.cisco.com/ast/soap}TotalDevicesFound")
        if total_elem is not None:
            total = int(total_elem.text or "0")
            if total >= self.config.risport_max_devices:
                logger.warning(
                    "TotalDevicesFound (%d) >= MaxReturnedDevices (%d), "
                    "results may be truncated",
                    total,
                    self.config.risport_max_devices,
                )

        devices = []
        ns_uri = "http://schemas.cisco.com/ast/soap"

        for cm_devices in root.iter(f"{{{ns_uri}}}CmDevices"):
            for item in cm_devices:
                device = self._parse_device(item, ns_uri)
                if device:
                    devices.append(device)

        return devices

    def _parse_device(self, item, ns_uri: str) -> dict | None:
        """Parse a single CmDevice item element."""
        device = {}
        field_map = {
            "Name": "name",
            "DeviceClass": "device_class",
            "Status": "status",
            "Protocol": "protocol",
            "Model": "model",
            "Description": "description",
            "DirNumber": "dir_number",
            "ActiveLoadID": "firmware",
            "NumOfLines": "num_lines",
            "TimeStamp": "timestamp",
            "Httpd": "httpd",
            "IsCtiControllable": "cti_controllable",
            "LoginUserId": "login_user",
        }

        for elem in item:
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag in field_map and elem.text and elem.text.strip():
                device[field_map[tag]] = elem.text.strip()

            # Extract first IP address
            if tag == "IPAddress":
                for ip_item in elem:
                    ip_elem = ip_item.find(f"{{{ns_uri}}}IP")
                    ip_type = ip_item.find(f"{{{ns_uri}}}IPAddrType")
                    if ip_elem is not None and ip_elem.text:
                        device["ip_address"] = ip_elem.text
                        if ip_type is not None and ip_type.text:
                            device["ip_type"] = ip_type.text

        return device if device.get("name") else None

    def _to_metrics(self, devices):
        """Convert device list to Prometheus metrics."""
        server_name = self.server.name

        # Deduplicate devices by name (same device may appear on multiple nodes)
        seen = {}
        for d in devices:
            name = d.get("name", "")
            existing = seen.get(name)
            if existing is None:
                seen[name] = d
            elif d.get("status") == "Registered" and existing.get("status") != "Registered":
                seen[name] = d
            elif (
                d.get("timestamp", "0") > existing.get("timestamp", "0")
                and existing.get("status") != "Registered"
            ):
                seen[name] = d

        unique_devices = list(seen.values())

        # Aggregate counts by device_class and status
        counts = defaultdict(int)
        for d in unique_devices:
            dc = d.get("device_class", "Unknown")
            st = d.get("status", "Unknown")
            counts[(dc, st)] += 1

        # cucm_devices_total
        devices_total = GaugeMetricFamily(
            "cucm_devices_total",
            "Total number of CUCM devices by class and status",
            labels=["cucm_host", "device_class", "status"],
        )
        for (dc, st), count in sorted(counts.items()):
            devices_total.add_metric([server_name, dc, st], count)
        yield devices_total

        # cucm_phones_registered
        phones_reg = sum(
            1
            for d in unique_devices
            if d.get("device_class") == "Phone"
            and d.get("status") == "Registered"
        )
        phones_gauge = GaugeMetricFamily(
            "cucm_phones_registered",
            "Number of registered phones",
            labels=["cucm_host"],
        )
        phones_gauge.add_metric([server_name], phones_reg)
        yield phones_gauge

        # cucm_sip_trunks_total
        trunks = sum(
            1
            for d in unique_devices
            if d.get("device_class") == "SIPTrunk"
        )
        trunks_gauge = GaugeMetricFamily(
            "cucm_sip_trunks_total",
            "Total number of SIP trunks",
            labels=["cucm_host"],
        )
        trunks_gauge.add_metric([server_name], trunks)
        yield trunks_gauge

        # cucm_media_resources_registered
        media_reg = sum(
            1
            for d in unique_devices
            if d.get("device_class") == "MediaResources"
            and d.get("status") == "Registered"
        )
        media_gauge = GaugeMetricFamily(
            "cucm_media_resources_registered",
            "Number of registered media resources",
            labels=["cucm_host"],
        )
        media_gauge.add_metric([server_name], media_reg)
        yield media_gauge

        # cucm_risport_devices_returned
        returned_gauge = GaugeMetricFamily(
            "cucm_risport_devices_returned",
            "Number of devices in the last RISPort response",
            labels=["cucm_host"],
        )
        returned_gauge.add_metric([server_name], len(devices))
        yield returned_gauge

        # cucm_device_info (per-device info metric)
        if self.config.risport_device_info_enabled:
            info_gauge = GaugeMetricFamily(
                "cucm_device_info",
                "CUCM device information",
                labels=[
                    "cucm_host",
                    "device_name",
                    "ip_address",
                    "device_class",
                    "status",
                    "protocol",
                    "description",
                    "firmware",
                ],
            )
            for d in unique_devices:
                info_gauge.add_metric(
                    [
                        server_name,
                        d.get("name", ""),
                        d.get("ip_address", ""),
                        d.get("device_class", ""),
                        d.get("status", ""),
                        d.get("protocol", ""),
                        d.get("description", ""),
                        d.get("firmware", ""),
                    ],
                    1,
                )
            yield info_gauge
