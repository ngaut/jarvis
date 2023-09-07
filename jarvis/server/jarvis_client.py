import grpc
import json
import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc
from google.protobuf.json_format import MessageToJson


def run():
    channel = grpc.insecure_channel("localhost:51155")
    stub = jarvis_pb2_grpc.JarvisStub(channel)

    response = stub.Execute(
        jarvis_pb2.ExecuteRequest(
            task="test",
            agent_id="experiment-3-2",
        )
    )
    print(f"Jarvis client received: {response}")

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
            agent_id="344b712e193cc0986e4045abd60f37c6",
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")
    """

    """
    response = stub.ChainExecute(
        jarvis_pb2.GoalExecuteRequest(
            goal="collect top 3 stories bullet points from hacker news front page",
            agent_id="ce8d543c6b50ae0271b095b5c9242b65",
            skip_gen=True,
            enable_skill_library=True,
        )
    )
    print(f"Jarvis client received: {MessageToJson(response)}")
    """


if __name__ == "__main__":
    run()
