from a2a.utils import constants

METHOD_SEND_JSON_RPC_1_0 = "SendMessage"
METHOD_STREAM_JSON_RPC_1_0 = "SendStreamingMessage"

METHOD_SEND_JSON_RPC_0_3 = "message/send"
METHOD_STREAM_JSON_RPC_0_3 = "message/stream"

METHOD_STREAM_HTTP_JSON = "/message:stream"


PROTOCOL_JSON_RPC = constants.TransportProtocol.JSONRPC
PROTOCOL_HTTP_JSON = constants.TransportProtocol.HTTP_JSON
PROTOCOL_GRPC = constants.TransportProtocol.GRPC

PROTOCOL_VERSION_1_0 = constants.PROTOCOL_VERSION_1_0
PROTOCOL_VERSION_0_3 = constants.PROTOCOL_VERSION_0_3
