"""GRPC 相关处理模块"""

import grpc
from collections.abc import AsyncIterable

from a2a.server.request_handlers import RequestHandler
from a2a.server.request_handlers.grpc_handler import DefaultGrpcServerCallContextBuilder
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import GrpcHandler
from a2a.compat.v0_3.grpc_handler import CompatGrpcHandler
from a2a.types import a2a_pb2_grpc

from a2a.types import a2a_pb2
from a2a.compat.v0_3 import a2a_v0_3_pb2, a2a_v0_3_pb2_grpc

from a2a_common.constants import METHOD_SEND_JSON_RPC_1_0, METHOD_STREAM_JSON_RPC_1_0

# 使用普通 dict 以 id(context) 为 key 存储 method 标记，
# grpc._cython.cygrpc._ServicerContext 不支持 weakref，因此使用 id()。
_context_method_map: dict[int, str] = {}


class GRPCStreamingAwareContextBuilder(DefaultGrpcServerCallContextBuilder):
    """在 ServerCallContext.state['method'] 中写入本次 gRPC 调用的方法名。"""

    def build(self, context: grpc.aio.ServicerContext) -> ServerCallContext:
        server_call_context = super().build(context)
        method = _context_method_map.pop(id(context), None)
        if method:
            server_call_context.state["method"] = method
        return server_call_context


class StreamingAwareGrpcHandler(GrpcHandler):
    """继承 GrpcHandler，在调用前通过 context id 注入 method 标记。"""

    async def SendMessage(
        self,
        request: a2a_pb2.SendMessageRequest,
        context: grpc.aio.ServicerContext,
    ) -> a2a_pb2.SendMessageResponse:
        _context_method_map[id(context)] = METHOD_SEND_JSON_RPC_1_0
        return await super().SendMessage(request, context)

    async def SendStreamingMessage(
        self,
        request: a2a_pb2.SendMessageRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterable[a2a_pb2.StreamResponse]:
        _context_method_map[id(context)] = METHOD_STREAM_JSON_RPC_1_0
        async for item in super().SendStreamingMessage(request, context):
            yield item


class StreamingAwareCompatGrpcHandler(CompatGrpcHandler):
    """继承 CompatGrpcHandler，在调用前通过 context id 注入 method 标记。"""

    async def SendMessage(
        self,
        request: a2a_v0_3_pb2.SendMessageRequest,
        context: grpc.aio.ServicerContext,
    ) -> a2a_v0_3_pb2.SendMessageResponse:
        _context_method_map[id(context)] = METHOD_SEND_JSON_RPC_1_0
        return await super().SendMessage(request, context)

    async def SendStreamingMessage(
        self,
        request: a2a_v0_3_pb2.SendMessageRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterable[a2a_v0_3_pb2.StreamResponse]:
        _context_method_map[id(context)] = METHOD_STREAM_JSON_RPC_1_0
        async for item in super().SendStreamingMessage(request, context):
            yield item


def init_grpc_server(grpc_server: grpc.aio.Server, request_handler: RequestHandler):
    """初始化 GRPC 服务"""

    grpc_handler_servicer = StreamingAwareGrpcHandler(
        request_handler, GRPCStreamingAwareContextBuilder()
    )
    a2a_pb2_grpc.add_A2AServiceServicer_to_server(
        grpc_handler_servicer, grpc_server
    )

def init_compat_grpc_server(compat_grpc_server: grpc.aio.Server, request_handler: RequestHandler):
    """初始化 GRPC v0.3 兼容服务"""

    compat_grpc_handler_servicer = StreamingAwareCompatGrpcHandler(
        request_handler, GRPCStreamingAwareContextBuilder()
    )
    a2a_v0_3_pb2_grpc.add_A2AServiceServicer_to_server(
        compat_grpc_handler_servicer, compat_grpc_server
    )
