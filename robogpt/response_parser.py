from dataclasses import dataclass
from typing import Optional, Tuple, Callable, List
import json
import actions

TELL_USER_PREFIX = "TELL_USER:"
READ_FILE_PREFIX = "READ_FILE:"
WRITE_FILE_PREFIX = "WRITE_FILE:"
RUN_PYTHON_PREFIX = "RUN_PYTHON:"
SEARCH_ONLINE_PREFIX = "SEARCH_ONLINE:"
EXTRACT_INFO_PREFIX = "EXTRACT_INFO:"
SHUTDOWN_PREFIX = "SHUTDOWN"

@dataclass(frozen=True)
class Metadata:
    reason: str
    plan: list[str]
    speak: Optional[str] = None

def parse_metadata(lines: List[str]) -> Metadata:
    if not lines:
        raise ValueError("Missing metadata in the response.")
    try:
        metadata_text = "\n".join(lines).strip()
        metadata_json = json.loads(metadata_text)
        return Metadata(
            reason=metadata_json["reason"],
            plan=metadata_json["plan"],
            speak=metadata_json.get("speak"),
        )
    except Exception as e:
        raise ValueError(f"Failed to parse metadata: {str(e)}\nMetadata text:\n{metadata_text}")


class ActionParser:

    def __init__(self, prefix: str, parser: Callable[[str, List[str]], actions.Action]):
        self.prefix = prefix
        self.parser = parser

    def parse(self, first_line: str, lines: List[str]) -> Optional[actions.Action]:
        if first_line.startswith(self.prefix):
            return self.parser(first_line, lines)
        return None

def write_file_action_parser(first_line: str, lines: List[str]) -> actions.WriteFileAction:
    path = first_line[len(WRITE_FILE_PREFIX):].strip()
    content = "\n".join(lines[2:-1]).strip()
    return actions.WriteFileAction(path=path, content=content)

def extract_info_action_parser(first_line: str, _: List[str]) -> actions.ExtractInfoAction:
    parts = first_line[len(EXTRACT_INFO_PREFIX):].strip().split(",", 1)
    url = parts[0].strip().strip('"')
    instructions = parts[1].strip()
    return actions.ExtractInfoAction(url, instructions)

action_parsers = [
    ActionParser(TELL_USER_PREFIX, lambda line, _: actions.TellUserAction(line[len(TELL_USER_PREFIX):].strip())),
    ActionParser(READ_FILE_PREFIX, lambda line, _: actions.ReadFileAction(line[len(READ_FILE_PREFIX):].strip())),
    ActionParser(WRITE_FILE_PREFIX, write_file_action_parser),
    ActionParser(RUN_PYTHON_PREFIX, lambda line, _: actions.RunPythonAction(line[len(RUN_PYTHON_PREFIX):].strip())),
    ActionParser(SEARCH_ONLINE_PREFIX, lambda line, _: actions.SearchOnlineAction(line[len(SEARCH_ONLINE_PREFIX):].strip())),
    ActionParser(EXTRACT_INFO_PREFIX, extract_info_action_parser),
    ActionParser(SHUTDOWN_PREFIX, lambda _, __: actions.ShutdownAction()),
]

def parse_action(first_line: str, lines: List[str]) -> actions.Action:
    for parser in action_parsers:
        action = parser.parse(first_line, lines)
        if action is not None:
            return action
    raise ValueError(f"Unknown action type in response: {first_line}")

def parse(text: str) -> Tuple[actions.Action, Metadata]:
    if not text:
        raise ValueError("Empty input received. Cannot parse.")
    lines = text.splitlines()
    action = parse_action(lines[0], lines)
    print(actions, lines)
    metadata = parse_metadata(lines[1:])
    return action, metadata
