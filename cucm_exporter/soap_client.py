"""Low-level SOAP HTTP client for CUCM APIs."""

import logging

import requests
import urllib3

from cucm_exporter.constants import SOAP_ENVELOPE

logger = logging.getLogger(__name__)

# Suppress insecure HTTPS warnings (CUCM uses self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SOAPError(Exception):
    """Raised when a SOAP fault is returned."""


class SOAPClient:
    """Shared SOAP HTTP client for PerfMon and RISPort70 APIs."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        verify_ssl: bool = False,
        timeout: float = 10.0,
    ):
        self.base_url = f"https://{host}:{port}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = verify_ssl
        self.session.headers.update(
            {"Content-Type": "text/xml; charset=utf-8"}
        )

    def send(self, path: str, soap_action: str, body_xml: str) -> str:
        """Send a SOAP request and return the response body as a string.

        Args:
            path: API endpoint path (e.g. /perfmonservice2/services/PerfmonService)
            soap_action: SOAPAction header value
            body_xml: XML content to wrap inside the SOAP envelope body

        Returns:
            Raw XML response string

        Raises:
            SOAPError: If the response contains a SOAP fault
            requests.HTTPError: On HTTP-level errors (401, 500, etc.)
            requests.ConnectionError: On network connectivity failures
        """
        url = f"{self.base_url}{path}"
        envelope = SOAP_ENVELOPE.format(body=body_xml)

        logger.debug("SOAP request to %s action=%s", url, soap_action)

        response = self.session.post(
            url,
            data=envelope,
            headers={"SOAPAction": f'"{soap_action}"'},
            timeout=self.timeout,
        )
        response.raise_for_status()

        text = response.text

        # Check for SOAP faults
        if "<SOAP-ENV:Fault>" in text or "<soapenv:Fault>" in text:
            raise SOAPError(f"SOAP fault in response: {text[:500]}")

        return text

    def close(self):
        """Close the underlying HTTP session."""
        self.session.close()
