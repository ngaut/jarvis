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
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--timeout', type=int, default=1, help='Timeout for user input')
    parser.add_argument('--continuous', action='store_true', help='Continuous mode')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--replan', action='store_true', help='Create a new plan')
    parser.add_argument('--yaml', type=str, help='Path to the yaml file to execute plan from')
    parser.add_argument('--startseq', type=int, default=0, help='Starting sequence number')
    parser.add_argument('--goalfile', type=str, default='', help='Specify the goal description file for Jarvis')
    parser.add_argument('--compile', type=int, default=0, help='Translate plan into instructions with given task number')

    args = parser.parse_args()

    # Load configuration from YAML file
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    assistant_config = config.get('assistant', {})
    args.timeout = args.timeout or assistant_config.get('timeout', 30)
    args.verbose = args.verbose or assistant_config.get('verbose', False)
    args.continuous = args.continuous or assistant_config.get('continuous', False)
    args.replan = args.replan or assistant_config.get('replan', False)
    args.goalfile = args.goalfile or assistant_config.get('goalfile', '')

    # Logging file name and line number
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        stream=sys.stdout
    )

    print("Welcome to Jarvis, your personal assistant for everyday tasks!\n")

    os.makedirs("workspace", exist_ok=True)
    os.chdir("workspace")

    if args.yaml:
        # Load the JVM instructions from the YAML file
        with open(args.yaml, 'r') as f:
            task_instrs = yaml.safe_load(f)
        logging.info(f"Running JVM Instructions:\n{task_instrs}")

        # Make sure start_seq is within bounds
        start_seq = args.startseq
        if start_seq < 0 or start_seq >= len(task_instrs["instructions"]):
            print(f"Invalid start sequence number: {start_seq}")
            exit(1)

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
