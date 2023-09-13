import os
import time
import logging
import glob
from jarvis.extensions.jarvis_agent import JarvisAgent


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


def run():
    workspace_dir = "workspace/T6"
    skill_lib_dir = "skill_library"
    execution_dir = "xxxx"
    skills = ["extract_store_procedure_case", "convert_store_procedure_case"]

    os.makedirs(workspace_dir, exist_ok=True)
    os.chdir(workspace_dir)
    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    )

    agent = JarvisAgent(skill_lib_dir)

    for index, skill in enumerate(skills):
        if index > 1:
            logging.info(f"waitting for next skill {skill}")
            time.sleep(5)
        clear_files_in_directory(execution_dir)
        logging.info(f"executing skill: {skill}")
        response = agent.execute_skill(execution_dir, skill)
        print(response)


if __name__ == "__main__":
    run()
