from dataclasses import dataclass
from typing import Optional, Tuple, List
import json
import actions

TELL_USER_PREFIX = "TELL_USER:"
READ_FILE_PREFIX = "READ_FILE:"
WRITE_FILE_PREFIX = "WRITE_FILE:"
APPEND_FILE_PREFIX = "APPEND_FILE:"
RUN_PYTHON_PREFIX = "RUN_PYTHON:"
SEARCH_ONLINE_PREFIX = "SEARCH_ONLINE:"
EXTRACT_INFO_PREFIX = "EXTRACT_INFO:"
SHUTDOWN_PREFIX = "SHUTDOWN"
FIND_AND_REPLACE_PREFIX = "FIND_AND_REPLACE:"
LIST_DIRECTORY_PREFIX = "LIST_DIRECTORY:"

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

def find_metadata_lines(lines: List[str], content_start: int) -> Tuple[List[str], List[str]]:
    end_of_content = len(lines) - 1
    for i in range(len(lines) - 1, content_start, -1):
        if lines[i].startswith("```"):
            end_of_content = i
            break
    content_lines = lines[content_start:end_of_content]
    metadata_lines = lines[end_of_content + 1:]
    return content_lines, metadata_lines


def parse_write_file_action(first_line: str, lines: List[str]) -> Tuple[actions.WriteFileAction, List[str]]:
    path = first_line[len(WRITE_FILE_PREFIX):].strip()
    content_lines, metadata_lines = find_metadata_lines(lines, 2)
    content_str = "\n".join(content_lines)
    action = actions.WriteFileAction(path=path, content=content_str)
    return action, metadata_lines

def parse_append_file_action(first_line: str, lines: List[str]) -> Tuple[actions.AppendFileAction, List[str]]:
    path = first_line[len(APPEND_FILE_PREFIX):].strip()
    content_lines, metadata_lines = find_metadata_lines(lines, 2)
    content_str = "\n".join(content_lines)
    action = actions.AppendFileAction(path=path, content=content_str)
    return action, metadata_lines

def parse_extract_info_action(line: str) -> Tuple[actions.ExtractInfoAction, List[str]]:
    url, instruction = line[len(EXTRACT_INFO_PREFIX):].strip().split(",", 1)
    return actions.ExtractInfoAction(url, instruction), []

def parse_shutdown_action(first_line: str) -> Tuple[actions.Action, List[str]]:
    reason = first_line[len(SHUTDOWN_PREFIX):].strip()
    return actions.ShutdownAction(reason), []

def parse_find_and_replace_action(first_line: str, lines: List[str]) -> Tuple[actions.FindAndReplaceAction, List[str]]:
    path = first_line[len(FIND_AND_REPLACE_PREFIX):].strip()
    
    find_lines, remaining_lines = find_metadata_lines(lines, 1)
    replace_lines, metadata_lines = find_metadata_lines(remaining_lines, 2)
    
    find_str = "\n".join(find_lines)
    replace_str = "\n".join(replace_lines)

    return actions.FindAndReplaceAction(path, find_str, replace_str), metadata_lines

def parse_list_directory_action(first_line: str) -> Tuple[actions.ListDirectoryAction, List[str]]:
    path = first_line[len(LIST_DIRECTORY_PREFIX):].strip()
    return actions.ListDirectoryAction(path), []



action_parsers = [
    (TELL_USER_PREFIX, lambda line, _: (actions.TellUserAction(line[len(TELL_USER_PREFIX):].strip()), [])),
    (READ_FILE_PREFIX, lambda line, _: (actions.ReadFileAction(line[len(READ_FILE_PREFIX):].strip()), [])),
    (WRITE_FILE_PREFIX, parse_write_file_action),
    (APPEND_FILE_PREFIX, parse_append_file_action),
    (RUN_PYTHON_PREFIX, lambda line, _: (actions.RunPythonAction(line[len(RUN_PYTHON_PREFIX):].strip()), [])),
    (SEARCH_ONLINE_PREFIX, lambda line, _: (actions.SearchOnlineAction(line[len(SEARCH_ONLINE_PREFIX):].strip()), [])),
    (EXTRACT_INFO_PREFIX, parse_extract_info_action),
    (FIND_AND_REPLACE_PREFIX, parse_find_and_replace_action),
    (LIST_DIRECTORY_PREFIX, parse_list_directory_action),
    (SHUTDOWN_PREFIX, parse_shutdown_action),
]

def parse_action(first_line: str, lines: List[str]) -> Tuple[actions.Action, List[str]]:
    for prefix, parser in action_parsers:
        if first_line.startswith(prefix):
            return parser(first_line, lines)
    raise ValueError(f"Unknown action type in response: {first_line}")

def parse(text: str) -> Tuple[actions.Action, Metadata]:
    if not text:
        raise ValueError("Empty input received. Cannot parse.")
    print("Text:", text)

    lines = text.splitlines()
    action, metadata_lines = parse_action(lines[0], lines)

    if not metadata_lines:
        metadata = Metadata(reason="", plan=[])
    else:
        metadata = parse_metadata(metadata_lines)

    return action, metadata


