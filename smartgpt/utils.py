# Description: Utility functions
import logging

from smartgpt import jvm


def wrap_string_to_eval(text):
    return jvm.LAZY_EVAL_PREFIX + text + ")"

def strip_yaml(text):
    # remove the last "```" if it exists
    if text.endswith("```"):
        return text[:-3]
    return text
