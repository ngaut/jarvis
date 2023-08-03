from concurrent import futures
import grpc
import server.jarvis_pb2 as jarvis_pb2
import server.jarvis_pb2_grpc as jarvis_pb2_grpc

from extensions.smartgpt_agent import JarvisAgent

class JarvisServicer(jarvis_pb2_grpc.JarvisServicer, JarvisAgent):

    def Execute(self, request, context):
        # You can access the request parameters using request.task_id, request.task, etc.
        # TODO: Implement your service logic here
        print(self.name)
        return jarvis_pb2.ExecuteResponse(task_id=request.task_id, task=request.task, result="Success", error="")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    jarvis_pb2_grpc.add_JarvisServicer_to_server(JarvisServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()