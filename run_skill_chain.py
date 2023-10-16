import os
import time
import logging
import glob
import argparse
from jarvis.agent.jarvis_agent import JarvisAgent
import traceback


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


def pretty_output(exec_result):
    print("\n" + "-" * 50)
    print("Skill Execution Summary")
    print("-" * 50 + "\n")

    print(f"Skill Result: {exec_result.result}")
    print(f"Skill Error:  {exec_result.error}")

    if exec_result.task_infos:
        print("\n" + "=" * 50)
        print("Detailed Task Infos")
        print("=" * 50 + "\n")

    for task_info in exec_result.task_infos:
        print(f"Subtask: {task_info.task}")
        print(f"Result:  {task_info.result}")
        print(f"Error:   {task_info.error}\n")
        print("-" * 50 + "\n")

    print("End of Execution Summary")
    print("-" * 50 + "\n")


def execute(workspace_dir, skill_lib_dir, execution_dir, skills):
    os.makedirs(workspace_dir, exist_ok=True)
    os.chdir(workspace_dir)

    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        filename="chain_jarvis.log",
    )

    agent = JarvisAgent(skill_lib_dir)

    for index, skill in enumerate(skills):
        if index > 0:
            logging.info(f"waitting for next skill {skill}")
            print(f"waitting for next skill {skill}")
            time.sleep(5)
        clear_files_in_directory(execution_dir)
        logging.info(f"executing skill: {skill}")
        print(f"executing skill: {skill}")

        try:
            exec_result = agent.execute_skill(execution_dir, skill)
        except Exception as e:
            logging.error(f"Failed to execute skill: {skill}, error: {e}")
            logging.error(traceback.format_exc())
            return

        pretty_output(exec_result)


def run():
    parser = argparse.ArgumentParser(
        description="CLI for Jarvis Agent Skills Chain Execution"
    )
    parser.add_argument("--workspace", required=True, help="Workspace directory path")
    parser.add_argument(
        "--skill_dir", required=True, help="Skill library directory path"
    )
    parser.add_argument(
        "--execution_dir", required=True, help="Execution directory path"
    )
    parser.add_argument("--skills", required=True, help="Comma separated skills list")

    args = parser.parse_args()

    # Split comma-separated skills into a list
    skills_list = args.skills.split(",")
    execute(args.workspace, args.skill_dir, args.execution_dir, skills_list)


if __name__ == "__main__":
    run()
