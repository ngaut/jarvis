from dataclasses import dataclass
from typing import Optional, Tuple, List
import json
import regex
import actions

def preprocess_json(text: str) -> str:
    # Replace single quotes with double quotes for keys and string values
    text = regex.sub(r"([\s{,])(\w+|\'.*?\')(\s*):", r'\1"\2"\3:', text)
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
    # Preprocess the input text to handle common issues
    text = preprocess_json(text)

    # Find all JSON-like objects enclosed by '{' and '}'
    json_objects = regex.findall(r'(?<!\{)\{(?:[^{}]|(?R))*\}(?!\})', text, flags=regex.DOTALL)
    result = []

    for obj in json_objects:
        # Try to decode the JSON object with the attempt_json_decode function
        decoded_obj = attempt_json_decode(obj)

        if decoded_obj:
            result.append(decoded_obj)

    return result


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
        plan = metadata_json.get("plan", [])
        memory = metadata_json.get("memory", {})
        speak = metadata_json.get("speak", None)
        current_task_id = metadata_json.get("current_task_id", None)

        return Metadata(
            reason=reason,
            plan=plan,
            memory=memory,
            speak=speak,
            current_task_id=current_task_id,
        )
    except Exception as e:
        raise ValueError(f"Failed to parse metadata: {str(e)}\nMetadata JSON:\n{metadata_json}")

def parse(text: str) -> Tuple[Optional[actions.Action], Metadata]:
    # Check for empty input
    if not text:
        raise ValueError("Empty input received. Cannot parse.")
    
    print(f"\nparse Text:{text}\n")

    try:
        # Extract the JSON object from the input string
        json_start = text.find("{")
        if json_start == -1:
            raise ValueError("No JSON object found in input")
        json_text = text[json_start:]
        json_objects = extract_json_objects(json_text)

        # Handle different capitalization forms of the "action" key
        data = {}
        for obj in json_objects:
            data.update(obj)
        print(f"\ndata:{data}\n")
        action_data = data.get("action", data.get("Action", data.get("ACTION")))

        # Create an Action object from the action data (if it exists)
        if action_data:
            action = actions.Action.from_dict(action_data)
        else:
            action = actions.Action.from_dict(data)

        # Parse the metadata
        metadata = parse_metadata(data)
        return action, metadata

    except ValueError as e:
        raise ValueError(f"Failed to parse input: {str(e)}, text:{text}\n")
    except Exception as e:
        raise Exception(f"Unexpected error occurred: {str(e)}, text:{text}\n")


