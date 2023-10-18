import os
import logging
import glob
from typing import Dict, Optional, Union, List, Any, Tuple

from autogen import ConversableAgent
from autogen import UserProxyAgent
from autogen import Agent

from jarvis.agent.jarvis_agent import JarvisAgent, EMPTY_FIELD_INDICATOR

def clear_files_in_directory(directory_path):
    file_patterns = ["*.yaml", "*.json", "*.txt"]
    for pattern in file_patterns:
        files_to_delete = glob.glob(os.path.join(directory_path, pattern))
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                logging.info(f"Remove file: {file_path}")
            except Exception as e:
                logging.info(f"Failed to remove {file_path}: {e}")


class JarvisExecutor(ConversableAgent):
    def __init__(self, skill_lib_dir="skill_library", execution_dir="autogen_execution"):
        super().__init__(
            name="jarvis executor",
            system_message="Jarvis executes your task.",
            is_termination_msg=lambda x: x.get("content") == "TERMINATE",
            human_input_mode="NEVER",
        )

        self.register_reply([Agent, None], JarvisExecutor.execute_task_and_replay)
        self.agent = JarvisAgent(skill_lib_dir)
        self.execution_dir = execution_dir


    def execute_task_and_replay(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Any] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        if messages is None or len(messages) == 0:
            return True, "Please provide a task description."
        
        task = messages[-1]["content"]

        try:
            response = self.agent.execute_with_skill_selection(self.execution_dir, task)
        except Exception as e:
            return True, str(e)
        
        if response.error:
            return True, response.error
        
        if response.result != EMPTY_FIELD_INDICATOR:
            return True, response.result
        
        return True, f"I had completed tasks {self.pretty_output(response)}."
    
    def pretty_output(self, exec_result):
        breaking1 = "-" * 50
        breaking2 = "=" * 50

        pretty_res = ""
        if exec_result.task_infos:
            pretty_res += f"\n{breaking2}\n"
            pretty_res += "Task Infos"
            pretty_res += f"\n{breaking2}\n\n"

        for task_info in exec_result.task_infos:
            pretty_res += f"Subtask: {task_info.task}\n"
            pretty_res += f"{breaking1}\n\n"

        return pretty_res

if __name__ == "__main__":
    workspace_dir = "workspace/T9"
    os.makedirs(workspace_dir, exist_ok=True)
    os.chdir(workspace_dir)

    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        filename="chain_jarvis.log",
    )

    config_list = [
        {
            'model': 'gpt-4',
            'api_key': os.getenv('OPENAI_API_KEY'),
        }
    ]
    jarvis = JarvisExecutor()
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="ALWAYS",
        is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    )

    first_task = input("What can I assist you with today? Input: ")
    print()
    # the assistant receives a message from the user, which contains the task description
    user_proxy.initiate_chat(jarvis, message=first_task)
