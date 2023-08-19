import shutil
import logging
import glob
import os
import yaml
from typing import Dict

from jarvis.smartgpt import gpt

def is_file_exist(file_path:str):
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return True
    
    return False

class Skill:
    name = 'skill_saver'
    description = "A skill that saves jarvis skill in a previous step within the skills folder. Not for writing code."

    def __init__(self, skill_register_dir:str):
        os.makedirs(skill_register_dir, exist_ok=True)
        self.skill_register_dir = skill_register_dir


        self.skills = {}
        skill_dirs = os.listdir(self.skill_register_dir)
        for skill_dir in skill_dirs:
            skill_name = skill_dir
            skill_objective, skill = self.load_skill_from_dir(os.path.join(self.skill_register_dir, skill_dir))
            self.skills[skill_name] = (skill_objective, skill)

    def load_skill(self, skill_name):
        skill = self.skills.get(skill_name)
        if skill is None:
            raise Exception(f"Skill '{skill_name}' not found.")
        
        return skill
    
    def clone_skill(self, skill_name, dest_dir):
        skill = self.skills.get(skill_name)
        if skill is None:
            raise Exception(
                f"Skill '{skill_name}' not found.")
        
        skill_objective, skill = skill
        try:
            shutil.copytree(os.path.join(self.skill_register_dir, skill_name), dest_dir)
        except Exception as e:
            logging.error("Error saving skill {resp}: {e}")
            raise e

        return None

    def execute(self, skill_dir):
        skill_objective, skill = self.load_skill_from_dir(skill_dir)

        sys_prompt = (
            "Please review the task and its execution plan, and give the task a suitable name\n"
        )
        user_prompt = f"Come up with a skill name (eg. 'get_weather') for the task({skill_objective}) execution plan:{skill}\n###\nSKILL_NAME:"

        skill_name = gpt.complete(
            prompt=user_prompt, model=gpt.GPT_3_5_TURBO_16K, system_prompt=sys_prompt
        )

        logging.info(f"Generate skill_name {skill_name} for jarvis plan under {skill_dir}")

        try:
            shutil.copytree(skill_dir, os.path.join(self.skill_register_dir, skill_name))
        except Exception as e:
            logging.error("Error saving skill {resp}: {e}")
            raise e
        
        self.skills[skill_name] = (skill_objective, skill)

        return None
    
    def load_skill_from_dir(self, skill_dir):
        plan_file = os.path.join(skill_dir, "plan.yaml")
        if os.path.exists(plan_file) and os.path.isfile(plan_file):
            plan = self.load_yaml(plan_file)
            skill_objective = plan.get("goal")
            if not skill_objective:
                raise ValueError(f"Skill objective is not defined in {plan_file}")
            return (skill_objective, plan)
        
        task_files = glob.glob("[0-9]*.yaml", root_dir=skill_dir)
        if len(task_files) != 1:
            raise ValueError(f"There should be exactly one task file under {skill_dir}")
        
        task_file = task_files[0]
        task = self.load_yaml(task_file)
        skill_objective = task.get("task")
        if not skill_objective:
            raise ValueError(f"Skill objective is not defined in {skill_dir}/{task_file}")
        return (skill_objective, task)
    
    def load_yaml(self, file_name: str) -> Dict:
        try:
            with open(file_name, 'r') as stream:
                return yaml.safe_load(stream)
        except Exception as e:
            logging.error(f"Error loading file {file_name}: {e}")
            raise

