import grpc
import server.jarvis_pb2 as jarvis_pb2
import server.jarvis_pb2_grpc as jarvis_pb2_grpc

def run():
    channel = grpc.insecure_channel('localhost:50051')
    stub = jarvis_pb2_grpc.JarvisStub(channel)
    response = stub.Execute(jarvis_pb2.ExecuteRequest(task="what's tidb"))
    print("Jarvis client received: " + response.result)

if __name__ == '__main__':
    run()
