import grpc
import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc
from google.protobuf.json_format import MessageToJson


def run():
    channel = grpc.insecure_channel("localhost:51155")
    stub = jarvis_pb2_grpc.JarvisStub(channel)

    # response = stub.Execute(jarvis_pb2.ExecuteRequest(task="tell me what's tidb"))
    # print("Jarvis client received: " + response.result)

    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal="tell me what's tidb",
            # agent_id="test",
            # skip_gen=True,
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")


if __name__ == "__main__":
    run()
