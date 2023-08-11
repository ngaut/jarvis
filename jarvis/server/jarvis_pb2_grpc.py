# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import jarvis.server.jarvis_pb2 as jarvis__pb2


class JarvisStub(object):
    """The Jarvis service provides an execute RPC method.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Execute = channel.unary_unary(
                '/server.Jarvis/Execute',
                request_serializer=jarvis__pb2.ExecuteRequest.SerializeToString,
                response_deserializer=jarvis__pb2.ExecuteResponse.FromString,
                )


class JarvisServicer(object):
    """The Jarvis service provides an execute RPC method.
    """

    def Execute(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_JarvisServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Execute': grpc.unary_unary_rpc_method_handler(
                    servicer.Execute,
                    request_deserializer=jarvis__pb2.ExecuteRequest.FromString,
                    response_serializer=jarvis__pb2.ExecuteResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'server.Jarvis', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class Jarvis(object):
    """The Jarvis service provides an execute RPC method.
    """

    @staticmethod
    def Execute(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/server.Jarvis/Execute',
            jarvis__pb2.ExecuteRequest.SerializeToString,
            jarvis__pb2.ExecuteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)