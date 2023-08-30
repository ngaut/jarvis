import openai
import json
import threading
import logging
import os
import uuid
import concurrent.futures
import time
from datetime import datetime

from jarvis.smartgpt import gpt
from jarvis.extensions.jarvis_agent import JarvisAgent, EMPTY_FIELD_INDICATOR

# Logging file name and line number
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
os.makedirs("workspace", exist_ok=True)
os.chdir("workspace")


OBJECTIVE_EXAMPLE = {
    "objective": "Research untapped.vc",
    "examples": [
        {
            "id": 1,
            "task": "Conduct a web search on 'untapped.vc' to gather information about the company, its investments, and its impact in the startup ecosystem.",
            "skill": "jarvis",
            "dependent_task_ids": [],
            "status": "incomplete",
        },
        {
            "id": 2,
            "task": "Based on the results from the first web search, perform a follow-up web search to explore specific areas of interest or investment strategies of 'untapped.vc'.",
            "skill": "jarvis",
            "dependent_task_ids": [1],
            "status": "incomplete",
        },
        {
            "id": 3,
            "task": "Use text_completion to summarize the findings from the initial web search on 'untapped.vc' and provide key insights.",
            "skill": "jarvis",
            "dependent_task_ids": [1],
            "status": "incomplete",
        },
        {
            "id": 4,
            "task": "Use text_completion to summarize the findings from the follow-up web search and highlight any additional information or insights.",
            "skill": "jarvis",
            "dependent_task_ids": [2],
            "status": "incomplete",
        },
        {
            "id": 5,
            "task": "Combine the summaries from the initial and follow-up web searches to provide a comprehensive overview of 'untapped.vc' and its activities.",
            "skill": "jarvis",
            "dependent_task_ids": [3, 4],
            "status": "incomplete",
        },
    ],
}


class TaskRegistry:
    def __init__(self):
        self.tasks = []
        # Initialize the lock
        self.lock = threading.Lock()

    def create_tasklist(self, objective, skill_descriptions):
        prompt = (
            f"You are an expert task list creation AI tasked with creating a  list of tasks as a JSON array, considering the ultimate objective of your team: {objective}.\n\n"
            f"Create a very short task list based on the objective, the final output of the last task will be provided back to the user. Limit tasks types to those that can be completed with the available skills listed below. Task description should be detailed.###"
            f"AVAILABLE SKILLS: {skill_descriptions}.###"
            f"RULES:"
            f"Do not use skills that are not listed."
            f"Always include one skill."
            f"dependent_task_ids should always be an empty array, or an array of numbers representing the task ID it should pull results from."
            f"Make sure all task IDs are in chronological order.###\n"
            f"EXAMPLE OBJECTIVE={json.dumps(OBJECTIVE_EXAMPLE['objective'])}"
            f"TASK LIST={json.dumps(OBJECTIVE_EXAMPLE['examples'])}"
            f"OBJECTIVE={objective}"
            f"TASK LIST="
        )

        print("\033[90m\033[3m" + "\nInitializing...\n" + "\033[0m")
        response = gpt.complete(
            prompt=prompt, model=gpt.GPT_4, system_prompt="You are a task creation AI."
        )

        try:
            task_list = json.loads(response)
            self.tasks = task_list
        except Exception as error:
            print(error)

    def execute_task(self, i, task, skill, task_outputs, objective):
        p_nexttask = (
            "\033[92m\033[1m"
            + "\n*****NEXT TASK ID:"
            + str(task["id"])
            + "*****\n"
            + "\033[0m\033[0m"
        )
        p_nexttask += f"\033[ EExecuting task {task.get('id')}: {task.get('task')}) [{task.get('skill')}]\033[)"
        print(p_nexttask)
        # Get the outputs of the dependent tasks
        dependent_task_outputs = (
            {dep: task_outputs[dep]["output"] for dep in task["dependent_task_ids"]}
            if "dependent_task_ids" in task
            else {}
        )
        # Execute the skill
        # print("execute:"+str([task['task'], dependent_task_outputs, objective]))
        task_output = skill(
            task.get("id"), task["task"], dependent_task_outputs, objective
        )
        print(
            "\033[93m\033[1m"
            + "\nTask Output (ID:"
            + str(task["id"])
            + "):"
            + "\033[0m\033[0m"
        )
        print("TASK: " + str(task["task"]))
        print("OUTPUT: " + str(task_output))
        return i, task_output

    def reorder_tasks(self):
        self.tasks = sorted(self.tasks, key=lambda task: task["id"])

    def add_task(self, task, after_task_id):
        # Get the task ids
        task_ids = [t["id"] for t in self.tasks]

        # Get the index of the task id to add the new task after
        insert_index = (
            task_ids.index(after_task_id) + 1
            if after_task_id in task_ids
            else len(task_ids)
        )

        # Insert the new task
        self.tasks.insert(insert_index, task)
        self.reorder_tasks()

    def update_tasks(self, task_update):
        for task in self.tasks:
            if isinstance(task_update["id"], str):
                task_update["id"] = int(task_update["id"])
            if task["id"] == task_update["id"]:
                # This merges the original task dictionary with the update, overwriting only the fields present in the update.
                task.update(task_update)
                self.reorder_tasks()

    def reflect_on_output(self, task_output, skill_descriptions):
        with self.lock:
            example = [
                [
                    {
                        "id": 3,
                        "task": "New task 1 description",
                        "skill": "text_completion_skill",
                        "dependent_task_ids": [2],
                        "status": "complete",
                    },
                    {
                        "id": 4,
                        "task": "New task 2 description",
                        "skill": "text_completion_skill",
                        "dependent_task_ids": [3],
                        "status": "incomplete",
                    },
                ],
                [2, 3],
                [
                    {
                        "id": 5,
                        "task": "Complete the objective and provide a final report",
                        "skill": "text_completion_skill",
                        "dependent_task_ids": [1, 2, 3, 4],
                        "status": "incomplete",
                    }
                ],
            ]

            prompt = (
                f"You are an expert task manager, review the output of last task and the current task list, and decide whether new tasks need to be added to enhance the execution plan.\n"
                f"As you add a new task, see if there are any tasks that need to be updated (such as updating dependencies for the task need its output)."
                f"Use the current task list as reference."
                f"Do not add duplicate tasks to those in the current task list."
                f"Only provide JSON as your response without further comments."
                f"Every new and updated task must include all variables, even they are empty array."
                f"Dependent IDs must be smaller than the ID of the task."
                f"New tasks IDs should be no larger than the last task ID."
                f"Always select at least one skill."
                f"Task IDs should be unique and in chronological order."
                f"Do not change the status of complete tasks."
                f"Only add skills from the AVAILABLE SKILLS, using the exact same spelling."
                f"Provide your array as a JSON array with double quotes. The first object is new tasks to add as a JSON array, the second array lists the ID numbers where the new tasks should be added after (number of ID numbers matches array), and the third object provides the tasks that need to be updated."
                f"Make sure to keep dependent_task_ids key, even if an empty array."
                f"AVAILABLE SKILLS: {skill_descriptions}.###"
                f"\n###Here is the last task output: {task_output}"
                f"\n###Here is the current task list: {self.tasks}"
                f"\n###Here are the performance ervaluations to follow:"
                " 1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities."
                " 2. Constructively self-criticize your big-picture behavior constantly."
                " 2. Reflect on past decisions and strategies to refine your approach."
                " 3. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps."
                f"\n###EXAMPLE OUTPUT FORMAT = {json.dumps(example)}"
                f"\nEnsure that the output is a valid JSON array."
                f"\n###OUTPUT = "
            )
            print(
                "\033[90m\033[3m"
                + "\nReflecting on task output to generate new tasks if necessary...\n"
                + "\033[0m"
            )

            response = gpt.complete(
                prompt=prompt,
                model=gpt.GPT_4,
                system_prompt="You are a task creation AI.",
            )

            print("\n#" + response)

            # Check if the returned result has the expected structure
            if isinstance(response, str):
                try:
                    task_list = json.loads(response)
                    # print("RESULT:")

                    # print(task_list)
                    # return [],[],[]
                    return task_list[0], task_list[1], task_list[2]
                except Exception as error:
                    print(error)
                    raise ValueError("Invalid task list structure in the output")

            else:
                raise ValueError("Invalid task list structure in the output")

    def get_tasks(self):
        """
        Returns the current list of tasks.

        Returns:
        list: the list of tasks.
        """
        return self.tasks

    def get_task(self, task_id):
        """
        Returns a task given its task_id.

        Parameters:
        task_id : int
            The unique ID of the task.

        Returns:
        dict
            The task that matches the task_id.
        """
        matching_tasks = [task for task in self.tasks if task["id"] == task_id]

        if matching_tasks:
            return matching_tasks[0]
        else:
            print(f"No task found with id {task_id}")
            return None

    def print_tasklist(self, task_list):
        p_tasklist = "\033[95m\033[1m" + "\n*****TASK LIST*****\n" + "\033[0m"
        for t in task_list:
            dependent_task_ids = t.get("dependent_task_ids", [])
            dependent_task = ""
            if dependent_task_ids:
                dependent_task = f"\033[31m<dependencies: {', '.join([f'#{dep_id}' for dep_id in dependent_task_ids])}>\033[0m"
            status_color = "\033[32m" if t.get("status") == "completed" else "\033[31m"
            p_tasklist += f"\033[1m{t.get('id')}\033[0m: {t.get('task')} {status_color}[{t.get('status')}]\033[0m \033[93m[{t.get('skill')}] {dependent_task}\033[0m\n"
        print(p_tasklist)


class JarvisAgentTools:
    def __init__(self):
        self.agent = JarvisAgent()
        self.previous_tasks = []
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.subdir = f"{unique_id}-{timestamp}"
        print(f"initial jarvis agent under subdir: {self.subdir}")

    @property
    def name(self) -> str:
        return self.agent.name

    @property
    def description(self) -> str:
        return self.agent.description

    def exec(
        self, task_id: int, task: str, dependent_tasks: dict, objective: str
    ) -> str:
        previous_tasks = []
        for previous_task_id in dependent_tasks.keys():
            for previous_task in self.previous_tasks:
                if previous_task.task_num == previous_task_id:
                    previous_tasks.append(previous_task_id)

        while True:
            task_info = self.agent.execute(
                self.subdir, objective, task, previous_tasks, task_num=task_id
            )
            assert task_info is not None, "last_task_info is None"
            if task_info.result != EMPTY_FIELD_INDICATOR:
                break
            print(f"Retring.... cause of empty result of task: {task_info}")

        self.previous_tasks.append(task_info.task_num)
        return task_info.result


# Set OBJECTIVE
OBJECTIVE = """
Compose a captivating tweet about the trending AI projects from the last 28 days, using trending data from https://ossinsight.io/collections/artificial-intelligence/.  Here's how to do it:

Success Criteria:

- The tweet must summarizes overall trends in AI projects from the last 28 days.
- 1-3 specific projects need to be featured in the tweet. These projects may rise rapidly in rankings, or github stars count growth rate is ahead of other projects. Make sure your selection is diverse to represent different observed trends.
- Collect and summarize recent developments (news) of selected projects to ensure that news is timely (nearly a month, current Date: 2023-07-27) and eye-catching
- The tweet should be engaging, amusing, and adheres to the Twitter's character limit.

Current Date: 2023-07-27
"""
REFLECTION = True

##### START MAIN LOOP########

# Print OBJECTIVE
print("\033[96m\033[1m" + "\n*****OBJECTIVE*****\n" + "\033[0m\033[0m")
print(OBJECTIVE)

session_summary = ""

jarvis = JarvisAgentTools()
skill_descriptions = f"[{jarvis.name}: {jarvis.description}]"
task_registry = TaskRegistry()

# Create the initial task list based on an objective
task_registry.create_tasklist(OBJECTIVE, skill_descriptions)

# Initialize task outputs
task_outputs = {
    i: {"completed": False, "output": None}
    for i, _ in enumerate(task_registry.get_tasks())
}

# Create a thread pool for parallel execution
with concurrent.futures.ThreadPoolExecutor() as executor:
    # Loop until all tasks are completed
    while not all(task["completed"] for task in task_outputs.values()):
        # Get the tasks that are ready to be executed (i.e., all their dependencies have been completed)
        tasks = task_registry.get_tasks()
        # Print the updated task list
        task_registry.print_tasklist(tasks)

        # Update task_outputs to include new tasks
        for task in tasks:
            if task["id"] not in task_outputs:
                task_outputs[task["id"]] = {"completed": False, "output": None}

        ready_tasks = [
            (task["id"], task)
            for task in tasks
            if all(
                (dep in task_outputs and task_outputs[dep]["completed"])
                for dep in task.get("dependent_task_ids", [])
            )
            and not task_outputs[task["id"]]["completed"]
        ]

        # Wait for the tasks to complete
        for task_id, task in ready_tasks:
            if task_outputs[task_id]["completed"]:
                continue

            task_id, output = task_registry.execute_task(
                task_id, task, jarvis.exec, task_outputs, OBJECTIVE
            )
            task_outputs[task_id]["output"] = output
            task_outputs[task_id]["completed"] = True

            # Update the task in the TaskRegistry
            task_registry.update_tasks(
                {"id": task_id, "status": "completed", "result": output}
            )

            completed_task = task_registry.get_task(task_id)
            print(
                f"\033[92mTask #{task_id}: {completed_task.get('task')} \033[0m\033[92m[COMPLETED]\033[0m\033[92m[{completed_task.get('skill')}]\033[0m"
            )

            # Reflect on the output
            if output:
                session_summary += (
                    json.dumps(completed_task) + "\n" + str(output) + "\n"
                )

                if REFLECTION == True:
                    (
                        new_tasks,
                        insert_after_ids,
                        tasks_to_update,
                    ) = task_registry.reflect_on_output(output, skill_descriptions)
                    # Insert new tasks
                    for new_task, after_id in zip(new_tasks, insert_after_ids):
                        task_registry.add_task(new_task, after_id)

                    # Update existing tasks
                    for task_to_update in tasks_to_update:
                        task_registry.update_tasks(task_to_update)

        # print(task_outputs.values())
        if all(task["status"] == "completed" for task in task_registry.tasks):
            print("All tasks completed!")
            break

        # Short delay to prevent busy looping
        time.sleep(0.1)

    # Print session summary
    print("\033[96m\033[1m" + "\n*****SAVING FILE...*****\n" + "\033[0m\033[0m")
    file = open(f'output_{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.txt', "w")
    file.write(session_summary)
    file.close()
    print("...file saved.")
    print("END")
    executor.shutdown()
