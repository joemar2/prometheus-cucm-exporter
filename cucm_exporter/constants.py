"""Constants for the CUCM Prometheus exporter."""

# SOAP envelope wrapper
SOAP_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope'
    ' xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:soap="http://schemas.cisco.com/ast/soap">'
    '<soapenv:Header/>'
    '<soapenv:Body>{body}</soapenv:Body>'
    '</soapenv:Envelope>'
)

# API paths
PERFMON_PATH = "/perfmonservice2/services/PerfmonService"
RISPORT_PATH = "/realtimeservice2/services/RISService70"

# SOAP XML body templates
PERFMON_COLLECT_BODY = (
    "<soap:perfmonCollectCounterData>"
    "<soap:Host>{host}</soap:Host>"
    "<soap:Object>{object_name}</soap:Object>"
    "</soap:perfmonCollectCounterData>"
)

PERFMON_LIST_COUNTER_BODY = (
    "<soap:perfmonListCounter>"
    "<soap:Host>{host}</soap:Host>"
    "</soap:perfmonListCounter>"
)

PERFMON_LIST_INSTANCE_BODY = (
    "<soap:perfmonListInstance>"
    "<soap:Host>{host}</soap:Host>"
    "<soap:Object>{object_name}</soap:Object>"
    "</soap:perfmonListInstance>"
)

RISPORT_SELECT_CM_DEVICE_BODY = (
    "<soap:selectCmDevice>"
    "<soap:StateInfo></soap:StateInfo>"
    "<soap:CmSelectionCriteria>"
    "<soap:MaxReturnedDevices>{max_devices}</soap:MaxReturnedDevices>"
    "<soap:DeviceClass>Any</soap:DeviceClass>"
    "<soap:Model>255</soap:Model>"
    "<soap:Status>Any</soap:Status>"
    "<soap:NodeName></soap:NodeName>"
    "<soap:SelectBy>Name</soap:SelectBy>"
    "<soap:SelectItems>"
    "<soap:item><soap:Item>*</soap:Item></soap:item>"
    "</soap:SelectItems>"
    "<soap:Protocol>Any</soap:Protocol>"
    "<soap:DownloadStatus>Any</soap:DownloadStatus>"
    "</soap:CmSelectionCriteria>"
    "</soap:selectCmDevice>"
)

# XML namespaces
NS = {"ns1": "http://schemas.cisco.com/ast/soap"}

# Default PerfMon objects to collect (17 objects)
DEFAULT_PERFMON_OBJECTS = [
    # Core call processing
    "Cisco CallManager",
    "Cisco CallManager System Performance",
    # SIP
    "Cisco SIP Stack",
    "Cisco SIP Station",
    # System resources
    "Memory",
    "Processor",
    "System",
    "Network Interface",
    "Partition",
    "TCP",
    # Services
    "DB Local_DSN",
    "DB Change Notification Server",
    "Number of Replicates Created and State of Replication",
    "Cisco TFTP",
    "Cisco Tomcat JVM",
    "Cisco Tomcat Connector",
    "Cisco Media Streaming App",
]

# Device status mapping (RISPort70 uses string status in response)
DEVICE_STATUS_VALUES = {
    "Registered",
    "Unregistered",
    "UnRegistered",
    "Rejected",
    "PartiallyRegistered",
    "Unknown",
    "Any",
}

# DeviceClass values returned by RISPort70
DEVICE_CLASS_VALUES = {
    "Phone",
    "Gateway",
    "H323",
    "Cti",
    "VoiceMail",
    "MediaResources",
    "HuntList",
    "SIPTrunk",
    "Unknown",
}
