from dataclasses import dataclass
from typing import Optional, Tuple, List
import json
import re
import actions

@dataclass(frozen=True)
class Metadata:
    reason: str
    plan: dict[int, str]
    memory: dict[str, str]
    speak: Optional[str] = None
    current_task_id: Optional[int] = None

def parse_metadata(metadata_json: dict) -> Metadata:
    try:
        reason = metadata_json.get("reason", "")
        plan = metadata_json.get("plan", {})
        memory = metadata_json.get("memory", {})
        speak = metadata_json.get("speak", None)
        current_task_id = metadata_json.get("current_task_id")

        return Metadata(
            reason=reason,
            plan={int(k): v for k, v in plan["tasks"].items()},
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

   # extract json from the text, ignoring any text before the first {, and and any text after the last }
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start == -1 or json_end == -1:
        raise ValueError("No JSON found in input. Cannot parse.")
    json_text = text[json_start:json_end + 1]
    response_json = json.loads(json_text)
    metadata = parse_metadata(response_json)
    action_data = response_json["action"]
    action = actions.Action.from_dict(action_data)

    return action, metadata
