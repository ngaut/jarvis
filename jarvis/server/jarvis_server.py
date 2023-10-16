import os
import logging

from datetime import datetime
import hashlib
from concurrent import futures
import grpc
from typing import Optional
import traceback


import jarvis.server.jarvis_pb2 as jarvis_pb2
import jarvis.server.jarvis_pb2_grpc as jarvis_pb2_grpc
from jarvis.agent.jarvis_agent import JarvisAgent, EMPTY_FIELD_INDICATOR


class JarvisServicer(jarvis_pb2_grpc.JarvisServicer, JarvisAgent):
    def __init__(self, skill_library_dir: Optional[str] = None):
        self.agent = JarvisAgent(skill_library_dir)

    def Execute(self, request, context):
        # You can access the request parameters using request.task_id, request.task, etc.
        if len(request.task.strip()) <= 0:
            return jarvis_pb2.ExecuteResponse(
                executor_id=request.executor_id,
                task_id=request.task_id,
                error="task is not provided",
            )
        task = request.task.strip()
        goal = ""
        if len(request.goal.strip()) > 0:
            goal = request.goal.strip()

        if len(request.executor_id.strip()) > 0:
            executor_id = request.executor_id.strip()
        else:
            executor_id = hashlib.md5(f"{goal}-{datetime.now()}".encode()).hexdigest()

        task_id = None
        if request.task_id > 0:
            task_id = request.task_id

        dependent_tasks = request.dependent_tasks
        enable_skill_library = request.enable_skill_library
        skip_gen = request.skip_gen

        retry_num = 0
        task_info = None
        while retry_num < 3:
            try:
                task_info = self.agent.execute(
                    executor_id,
                    goal,
                    task,
                    dependent_tasks,
                    task_id,
                    skip_gen,
                    enable_skill_library,
                )
            except Exception as e:
                return jarvis_pb2.ExecuteResponse(
                    executor_id=executor_id,
                    task_id=task_id,
                    task=task,
                    result="",
                    error=str(e),
                )

            if task_info is not None and task_info.result != EMPTY_FIELD_INDICATOR:
                break
            print(f"Retring.... cause of empty result of task: {task_info}")
            retry_num += 1

        if retry_num >= 3:
            return jarvis_pb2.ExecuteResponse(
                executor_id=executor_id,
                task_id=task_id,
                task=task,
                result="",
                error="failed to get execution result",
            )

        return jarvis_pb2.ExecuteResponse(
            executor_id=executor_id,
            task_id=task_info.task_num,
            task=task_info.task,
            result=task_info.result,
        )

    def ExecutePlan(self, request, context):
        if len(request.goal.strip()) <= 0:
            return jarvis_pb2.ExecuteResponse(
                error="goal is not provided",
            )
        goal = request.goal.strip()

        if len(request.executor_id.strip()) > 0:
            executor_id = request.executor_id.strip()
        else:
            executor_id = hashlib.md5(f"{goal}-{datetime.now()}".encode()).hexdigest()

        enable_skill_library = request.enable_skill_library
        skip_gen = request.skip_gen
        try:
            exec_result = self.agent.execute_with_plan(
                executor_id,
                goal,
                skip_gen=skip_gen,
                enable_skill_library=enable_skill_library,
            )
        except Exception as e:
            logging.error(f"Failed to execute goal: {goal}, error: {e}")
            logging.error(traceback.format_exc())
            return jarvis_pb2.ExecuteResponse(
                executor_id=executor_id,
                goal=goal,
                error=str(e),
            )

        response = jarvis_pb2.ExecuteResponse(
            executor_id=executor_id,
            goal=goal,
            result=exec_result.result,
        )
        if exec_result.error is not None:
            response.error = exec_result.error

        for task_info in exec_result.task_infos:
            task_response = jarvis_pb2.ExecuteResponse(
                task=task_info.task,
                result=task_info.result,
            )
            if task_info.error is not None:
                task_response.error = task_info.error

            response.subtasks.append(task_response)
        return response

    def SaveSkill(self, request, context):
        if len(request.executor_id.strip()) <= 0:
            return jarvis_pb2.SaveSkillResponse(
                error="executor_id is not provided",
            )
        executor_id = request.executor_id.strip()
        skill_name = request.skill_name.strip()

        try:
            skill_name = self.agent.save_skill(executor_id, skill_name)
        except Exception as e:
            return jarvis_pb2.SaveSkillResponse(
                executor_id=executor_id,
                error=str(e),
            )

        return jarvis_pb2.SaveSkillResponse(
            executor_id=executor_id,
            result=f"skill is saved as {skill_name}",
        )


def serve():
    workspace_dir = "workspace"
    skill_lib_dir = "skill_library"
    os.makedirs(workspace_dir, exist_ok=True)
    os.chdir(workspace_dir)
    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        filename=f"grpc_jarvis.log",
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    jarvis_pb2_grpc.add_JarvisServicer_to_server(
        JarvisServicer(skill_library_dir=skill_lib_dir), server
    )
    server.add_insecure_port("[::]:51155")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
