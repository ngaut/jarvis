from dataclasses import dataclass
from typing import Optional, Tuple, List
import regex
import actions
import json
import logging
import os


@dataclass(frozen=True)
class Metadata:
    plan: List[str]
    notebook: dict[str, str]
    current_task_id: Optional[str] = None

    def __str__(self):
        return f"Metadata(\n  plan={self._pretty_list(self.plan)},\n  notebook={self._pretty_dict(self.notebook)},\n  current_task_id='{self.current_task_id}'\n)"

    def _pretty_list(self, lst):
        return "[\n" + ",\n".join(f"    '{item}'" for item in lst) + "\n  ]"

    def _pretty_dict(self, dct):
        return "{\n" + ",\n".join(f"    '{key}': '{value}'" for key, value in dct.items()) + "\n  }"
    
def parse_metadata(metadata_json: dict) -> Metadata:
    try:
        plan = metadata_json.get("plan", [])
        notebook = metadata_json.get("notebook", {})
        current_task_id = metadata_json.get("current_task_id", None)

        return Metadata(
            plan=plan,
            notebook=notebook,
            current_task_id=current_task_id,
        )
    except Exception as e:
        raise ValueError(f"parse_metadata: Failed to parse metadata: {str(e)}\nMetadata JSON:\n{metadata_json}")

def parse(text: str) -> Tuple[Optional[actions.Action], Optional[Metadata]]:
    # Check for empty input
    if not text:
        raise ValueError("parse: Empty input received. Cannot parse.")
    
    #logging.info(f"\nparse Text:{text}\n")

    try:
        # Try to decode json
        start = text.index('{')
        end = text.rindex('}')
        if start >= end:
            raise ValueError("parse: Failed to parse input as JSON object, You should response a valid json")
        data = json.loads(text[start:end+1])

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
    except json.JSONDecodeError as json_err:
        # Get the position of the error
        pos = json_err.pos
        start = max(0, pos - 20)
        end = min(len(json_err.doc), pos + 20)

        # Construct the context snippet
        context = json_err.doc[start:end]
        caret = " " * (pos - start) + "^"  # Caret pointing to the error position

        # Construct the error message
        error_message = f"Failed to parse input as JSON object, You should response a valid json. " \
                        f"Here is a snippet for context:\n\n{context}\n{caret}"

        # Log the error message
        logging.error(error_message)

        # Raise a new exception with the pretty error message
        raise ValueError(error_message)
        
    except Exception as e:
        logging.error("\n%s\n", e)
        raise ValueError("parse: Failed to parse input as JSON object, You should response a valid json")