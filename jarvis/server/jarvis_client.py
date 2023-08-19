import grpc
import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc
from google.protobuf.json_format import MessageToJson


def run():
    channel = grpc.insecure_channel("localhost:51155")
    stub = jarvis_pb2_grpc.JarvisStub(channel)

    # response = stub.Execute(jarvis_pb2.ExecuteRequest(task="Search on the internet and retrieve relevant URLs about TiDB.", agent_id="e09a0d3fd0feba4e5c8ae3d687c63368"))
    # print("Jarvis client received: " + response.result)

    """
    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal="give a research report on tidb cloud",
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")
    """

    """
    response = stub.SaveSkill(
        jarvis_pb2.SaveSkillRequest(
            agent_id="sj-hn-2-4",
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")
    """


if __name__ == "__main__":
    run()
