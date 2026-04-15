"""Convert CUCM counter names to Prometheus metric names."""

import re


def to_prometheus_name(object_name: str, counter_name: str) -> str:
    """Convert a CUCM object + counter name to a Prometheus metric name.

    Examples:
        ("Cisco CallManager", "CallsActive") -> "cucm_callmanager_calls_active"
        ("Memory", "% Mem Used") -> "cucm_memory_mem_used_percent"
        ("Processor", "% CPU Time") -> "cucm_processor_cpu_time_percent"
        ("Cisco SIP Stack", "InviteIns") -> "cucm_sip_stack_invite_ins"
    """
    obj_part = _normalize_object(object_name)
    counter_part = _normalize_counter(counter_name)
    name = f"cucm_{obj_part}_{counter_part}"
    # Collapse multiple underscores and strip edges
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    return name.lower()


def _normalize_object(name: str) -> str:
    """Normalize CUCM object name to snake_case.

    Object names are NOT CamelCase-split because they contain product
    names like "CallManager" that should stay as one word.
    """
    # Strip common prefixes
    name = re.sub(r"^Cisco\s+", "", name)
    # Replace hyphens, dots, slashes with spaces
    name = re.sub(r"[-./]", " ", name)
    # Replace spaces with underscores
    name = re.sub(r"\s+", "_", name)
    # Remove non-alphanumeric/underscore characters
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    return name.lower()


def _normalize_counter(name: str) -> str:
    """Normalize CUCM counter name to snake_case."""
    # Handle percent prefix: "% Mem Used" -> "Mem Used" with suffix
    has_percent = False
    if name.startswith("%"):
        has_percent = True
        name = name.lstrip("% ")

    result = _to_snake(name)

    if has_percent:
        result = result + "_percent"

    return result


def _to_snake(name: str) -> str:
    """Convert a mixed string (CamelCase, spaces, hyphens) to snake_case."""
    # Replace hyphens, dots, slashes with spaces
    name = re.sub(r"[-./]", " ", name)
    # Insert underscore before uppercase following lowercase or digit
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Insert underscore between consecutive uppercase and following lowercase
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # Replace spaces with underscores
    name = re.sub(r"\s+", "_", name)
    # Remove non-alphanumeric/underscore characters
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    return name.lower()
