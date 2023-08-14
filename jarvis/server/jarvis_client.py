import grpc
import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc


def run():
    channel = grpc.insecure_channel("localhost:51155")
    stub = jarvis_pb2_grpc.JarvisStub(channel)

    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal="tell me what's tidb",
        )
    )
    print(f"Jarvis client received: {response}")
    return

    response = stub.Execute(jarvis_pb2.ExecuteRequest(task="tell me what's tidb"))
    print("Jarvis client received: " + response.result)


if __name__ == "__main__":
    run()
