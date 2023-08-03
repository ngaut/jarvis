from datetime import datetime
import hashlib
from pydantic import BaseModel
from typing import Callable

from concurrent import futures
import grpc
import server.jarvis_pb2 as jarvis_pb2
import server.jarvis_pb2_grpc as jarvis_pb2_grpc

from extensions.smartgpt_agent import JarvisAgent, EMPTY_FIELD_INDICATOR

class JarvisServicer(jarvis_pb2_grpc.JarvisServicer, JarvisAgent):

    def __init__(self):
        self.agents = {}

    def Execute(self, request, context):
        # You can access the request parameters using request.task_id, request.task, etc.
        # TODO: Implement your service logic here

        if len(request.task.strip()) <= 0:
            return jarvis_pb2.ExecuteResponse(agent_id=request.agent_id, task_id=request.task_id, error="task is not provided")
        task = request.task.strip()

        agent_id = None
        agent = None
        if len(request.agent_id.strip()) > 0:
            agent_id = request.agent_id.strip()
            agent = self.agents.get(agent_id, None)

        goal = task
        if  agent is not None:
            goal = agent["goal"]

        if len(request.goal.strip()) > 0:
            if agent is not None and request.goal.strip() != goal:
                return jarvis_pb2.ExecuteResponse(agent_id=request.agent_id, task_id=request.task_id,  error=f"found agent, but goal is not matched:{request.goal.strip()} and {goal}. Please check your request")
            goal = request.goal.strip()

        dependent_tasks = request.dependent_tasks
        if agent is None and len(dependent_tasks) > 0:
            return jarvis_pb2.ExecuteResponse(agent_id=request.agent_id, task_id=request.task_id,  error="not found agent, but dependent tasks provied. Please check your request")
        
        if agent_id is None:
            agent_id = hashlib.md5(f"{goal}-{datetime.now()}".encode()).hexdigest()

        if agent is None:
            agent = {"executor":JarvisAgent(), "goal":goal, "previous_tasks":[]}
            self.agents[agent_id] = agent

        task_id = None
        if request.task_id > 0:
            task_id = request.task_id

        previous_tasks = []
        for dt_id in dependent_tasks:
            for pt in agent["previous_tasks"]:
                if dt_id == pt.task_id:
                    previous_tasks.append(pt)

        retry_num = 0
        task_info = None
        while retry_num < 3:
            task_info = agent["executor"](
                task, previous_tasks, goal, subdir=agent_id, task_num=task_id
            )
            if task_info is not None and task_info.result != EMPTY_FIELD_INDICATOR:
                break
            print(f"Retring.... cause of empty result of task: {task_info}")
            retry_num += 1

        if retry_num >= 3:
            return jarvis_pb2.ExecuteResponse(agent_id = agent_id, task_id=task_id, task=task, result="", error="failed to get execution result")

        task_info = jarvis_pb2.TaskInfo(task_id=task_id, task=task, result=task_info.result, metadata=task_info.metadata)
        agent["previous_tasks"].append(task_info)

        return jarvis_pb2.ExecuteResponse(agent_id = agent_id, task_id=task_info.task_id, task=task_info.task, result=task_info.result)  

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    jarvis_pb2_grpc.add_JarvisServicer_to_server(JarvisServicer(), server)
    server.add_insecure_port('[::]:51155')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()