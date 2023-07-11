# Description: Utility functions

from smartgpt import jvm


def wrap_string_to_eval(text):
    return jvm.LAZY_EVAL_PREFIX + text + ")"

def strip_yaml(text):
    # Strip whitespace (including newline) from end
    text = text.rstrip()

    # keep removing the last "```" if it exists
    while text.endswith("```"):
        text = text[:-3]
        text = text.rstrip()

    # if text starts with "```yaml\n", remove it
    if text.startswith("```yaml\n"):
        text = text[8:]

    return text

def sys_eval(text):
    return eval(text)

def str_to_bool(s):
    if isinstance(s, bool):
        return s
    elif isinstance(s, str):
        return s.lower() == 'true'
    else:
        return False