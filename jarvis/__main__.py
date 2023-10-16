import os
import sys
import argparse
import logging

import yaml

from jarvis.smartgpt import initializer
from jarvis.smartgpt import gpt
from jarvis.smartgpt import planner
from jarvis.smartgpt import instruction
from jarvis.smartgpt import compiler


PLANNER_MODEL = gpt.GPT_4
TRANSLATOR_MODEL = gpt.GPT_4

def run():
    # Initialize the Jarvis environment
    initializer.setup()

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    # parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--replan', action='store_true', help='Create a new plan')
    parser.add_argument('--yaml', type=str, help='Path to the yaml file to execute plan from')
    parser.add_argument('--goalfile', type=str, default='', help='Specify the goal description file for Jarvis')
    parser.add_argument('--compile', type=int, default=0, help='Translate plan into instructions with given task number')
    parser.add_argument('--workspace', type=str, default='workspace', help='Specify the workspace directory')

    args = parser.parse_args()

    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        stream=sys.stdout
    )

    print("Welcome to Jarvis, your personal assistant for everyday tasks!\n")

    os.makedirs(args.workspace, exist_ok=True)
    os.chdir(args.workspace)

    if args.yaml:
        # Load the JVM instructions from the YAML file
        with open(args.yaml, 'r') as f:
            task_instrs = yaml.safe_load(f)
        logging.info(f"Running JVM Instructions:\n{task_instrs}")

        interpreter = instruction.JVMInterpreter()
        interpreter.run(task_instrs["instructions"], task=task_instrs["task"])
    else:
        if args.replan:
            goal = ""
            if args.goalfile:
                if not os.path.isfile(args.goalfile):
                    logging.error(f"The goal file {args.goalfile} does not exist")
                    exit(1)
                with open(args.goalfile, 'r') as f:
                    goal = f.read()
            logging.info("Regenerate plan ...")
            planner.gen_plan(PLANNER_MODEL, goal)
        elif args.compile:
            logging.info(f"Tranlate the given task[{args.compile}] into JVM instructions ...")
            compiler.Compiler(TRANSLATOR_MODEL).compile_task_in_plan(args.compile)
        else:
            logging.info("Tranlate all tasks in plan ...")
            compiler.Compiler(TRANSLATOR_MODEL).compile_plan()


if __name__ == "__main__":
    run()
