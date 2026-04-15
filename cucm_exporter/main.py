"""Entry point for the CUCM Prometheus exporter."""

import argparse
import logging
import sys
import threading

from prometheus_client import REGISTRY, start_http_server

from cucm_exporter.config import Config
from cucm_exporter.collector import CUCMCollector
from cucm_exporter.soap_client import SOAPClient

logger = logging.getLogger("cucm_exporter")


def main():
    parser = argparse.ArgumentParser(
        description="Prometheus exporter for Cisco Unified Communications Manager"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Exporter HTTP port (overrides config)",
    )
    args = parser.parse_args()

    # Load configuration
    config = Config.load(args.config)
    if args.port:
        config.exporter_port = args.port

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Validate required config
    if not config.servers:
        logger.error(
            "No CUCM servers configured. Add a 'servers' list in the config "
            "file or set CUCM_HOST / CUCM_USERNAME / CUCM_PASSWORD env vars."
        )
        sys.exit(1)

    logger.info(
        "Starting CUCM exporter for %d server(s): %s",
        len(config.servers),
        ", ".join(s.name for s in config.servers),
    )
    logger.info(
        "PerfMon: %s (%d objects), RISPort: %s",
        "enabled" if config.perfmon_enabled else "disabled",
        len(config.perfmon_objects),
        "enabled" if config.risport_enabled else "disabled",
    )

    # Create one SOAP client per server and validate connectivity
    server_entries = []
    per_object_timeout = config.scrape_timeout / max(len(config.perfmon_objects), 1)

    for server in config.servers:
        soap_client = SOAPClient(
            host=server.host,
            port=server.port,
            username=server.username,
            password=server.password,
            verify_ssl=server.verify_ssl,
            timeout=per_object_timeout,
        )
        _validate_connectivity(soap_client, server)
        server_entries.append((server, soap_client))

    # Register collector
    collector = CUCMCollector(config, server_entries)
    REGISTRY.register(collector)

    # Start HTTP server
    logger.info("Serving metrics on port %d", config.exporter_port)
    start_http_server(config.exporter_port)

    # Block forever
    threading.Event().wait()


def _validate_connectivity(soap_client, server):
    """Test connectivity to a CUCM server on startup."""
    from cucm_exporter.constants import PERFMON_COLLECT_BODY, PERFMON_PATH

    try:
        body = PERFMON_COLLECT_BODY.format(
            host=server.host, object_name="Memory"
        )
        soap_client.send(
            path=PERFMON_PATH,
            soap_action="perfmonCollectCounterData",
            body_xml=body,
        )
        logger.info("[%s] Connectivity check passed", server.name)
    except Exception as e:
        logger.warning(
            "[%s] Connectivity check failed: %s. "
            "Exporter will start anyway; metrics will show cucm_up=0 "
            "until connectivity is restored.",
            server.name,
            e,
        )


if __name__ == "__main__":
    main()
