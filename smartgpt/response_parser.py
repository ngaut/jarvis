from dataclasses import dataclass
from typing import Optional, Tuple, List
import regex
import actions
import json
import logging

def preprocess_json(text: str) -> str:
    # Replace single quotes with double quotes for keys and string values
    text = regex.sub(r"([\s{,])(\w+|'(?:[^'\\]|\\.)*?')(\s*):", r'\1"\2"\3:', text)
    text = regex.sub(r"(:\s*)\'(.*?)\'", r'\1"\2"', text)

    # Remove trailing commas from objects and arrays
    text = regex.sub(r',\s*([\}\]])', r'\1', text)

    return text

def attempt_json_decode(json_text: str):
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        json_text = json_text.strip()
        if json_text.startswith('{') and json_text.endswith('}'):
            return attempt_json_decode('[' + json_text + ']')
        raise

def extract_json_objects(text: str) -> List:
    result = []
    stack = []
    start = -1

    for i, c in enumerate(text):
        if c == '{':
            stack.append(c)
            if len(stack) == 1:
                start = i
        elif c == '}':
            if stack and stack[-1] == '{':
                stack.pop()
                if not stack:
                    json_obj = preprocess_json(text[start:i+1])
                    result.append(json_obj)
            else:
                stack.clear()
                start = -1

    return result


@dataclass(frozen=True)
class Metadata:
    plan: List[str]
    memory: dict[str, str]
    current_task_id: Optional[str] = None

    def __str__(self):
        return f"Metadata(\n  plan={self._pretty_list(self.plan)},\n  memory={self._pretty_dict(self.memory)},\n  current_task_id='{self.current_task_id}'\n)"

    def _pretty_list(self, lst):
        return "[\n" + ",\n".join(f"    '{item}'" for item in lst) + "\n  ]"

    def _pretty_dict(self, dct):
        return "{\n" + ",\n".join(f"    '{key}': '{value}'" for key, value in dct.items()) + "\n  }"
    
def parse_metadata(metadata_json: dict) -> Metadata:
    try:
        plan = metadata_json.get("plan", [])
        memory = metadata_json.get("memory", {})
        current_task_id = metadata_json.get("current_task_id", None)

        return Metadata(
            plan=plan,
            memory=memory,
            current_task_id=current_task_id,
        )
    except Exception as e:
        raise ValueError(f"parse_metadata: Failed to parse metadata: {str(e)}\nMetadata JSON:\n{metadata_json}")

def parse(text: str) -> Tuple[Optional[actions.Action], Optional[Metadata]]:
    # Check for empty input
    if not text:
        raise ValueError("parse: Empty input received. Cannot parse.")
    
    logging.info(f"\nparse Text:{text}\n")

    try:
        # Try to parse the input as a valid JSON object
        data = json.loads(text)

        # Create an Action object from the action data (if it exists)
        action_data = data.get("action", data.get("Action", data.get("ACTION")))
        action = None
        if action_data:
            action = actions.Action.from_dict(action_data)
        
        if action is None:
            action = actions.Action.from_dict(data)

        # Parse the metadata
        metadata = parse_metadata(data)
        return action, metadata

    except ValueError:
        # If parsing as a JSON object fails, try to extract JSON object(s) from the input string
        json_objects = extract_json_objects(text)
        if not json_objects:
            raise ValueError(f"Failed to parse input as JSON object, please fix it:: {text}")
        
        # Create an Action object and parse the metadata for each JSON object separately
        action = None
        metadata = None
        for json_text in json_objects:
            try:
                data = json.loads(json_text)

                # Create an Action object from the action data (if it exists)
                action_data = data.get("action", data.get("Action", data.get("ACTION")))
                if action_data:
                    action = actions.Action.from_dict(action_data)
                
                if action is None:
                    action = actions.Action.from_dict(data)

                # Parse the metadata
                metadata = parse_metadata(data)
            except Exception as e:
                raise ValueError(f"Error: {str(e)}, Failed to parse input as JSON object, please fix it: {json_text}\n")
        
        return action, metadata
