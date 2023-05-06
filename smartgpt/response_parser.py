from dataclasses import dataclass
from typing import Optional, Tuple, List
import json
import re
import actions
import json


def extract_json_objects(text):
    # Only keep text that between first '{' and last '}'
    text = re.sub(r'^.*?({.*}).*$', r'\1', text, flags=re.DOTALL)

    # Replace single quotes with double quotes
    text = text.replace("'", '"')

    # Remove trailing commas from objects and arrays
    text = re.sub(r'(?<=[\}\]]),\s*', '', text)

    # Add enclosing square brackets to JSON arrays if missing
    if not text.startswith('[') and '}' not in text:
        text = f'[{text}]'

    json_objects = []
    idx = 0

    while idx < len(text):
        try:
            json_obj, json_end_idx = json.JSONDecoder().raw_decode(text[idx:])
            json_objects.append(json_obj)
            idx += json_end_idx
        except ValueError:
            idx += 1

    return json_objects





@dataclass(frozen=True)
class Metadata:
    reason: str
    plan: List[str]
    memory: dict[str, str]
    speak: Optional[str] = None
    current_task_id: Optional[str] = None

def parse_metadata(metadata_json: dict) -> Metadata:
    try:
        reason = metadata_json.get("reason", "")
        plan = metadata_json.get("plan", {})
        memory = metadata_json.get("memory", {})
        speak = metadata_json.get("speak", None)
        current_task_id = metadata_json.get("current_task_id")
        task_list = plan.get("tasks", [])

        return Metadata(
            reason=reason,
            plan=task_list,
            memory=memory,
            speak=speak,
            current_task_id=current_task_id["id"] if current_task_id else None,
        )
    except Exception as e:
        raise ValueError(f"Failed to parse metadata: {str(e)}\nMetadata JSON:\n{metadata_json}")

def parse(text: str) -> Tuple[actions.Action, Metadata]:
    if not text:
        raise ValueError("Empty input received. Cannot parse.")

    print(f"Text:{text}")

    # Extract JSON objects from the text
    json_objects = extract_json_objects(text)

    if not json_objects:
        raise ValueError("No JSON found in input. Cannot parse.")

    # Create a dictionary from the key-value pairs in the input list
    response_json = {json_objects[i]: json_objects[i+1] for i in range(0, len(json_objects), 2)}

    # Handle different capitalization forms of the "action" key
    action_data = response_json.get("action", response_json.get("Action", response_json.get("ACTION")))

    try:
        metadata = parse_metadata(response_json)
        action = actions.Action.from_dict(action_data)
        return action, metadata
    except Exception as e:
        raise ValueError(f"Failed to parse json: {str(e)}, text:{text}\n")



