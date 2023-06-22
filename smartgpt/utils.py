# Description: Utility functions


import logging
import jvm


LAZY_EVAL_PREFIX = "@eval("

def wrap_string_to_eval(text):
    return LAZY_EVAL_PREFIX + text + ")"

    
def eval_expression(text, lazy_eval_prefix=LAZY_EVAL_PREFIX):
    # find last occurrence of "@eval("
    start = text.rfind(lazy_eval_prefix)
    if start == -1:
        return None

    prefix_len = len(lazy_eval_prefix)
    # find the corresponding closing tag with parentheses balance
    rest = text[start+prefix_len:]
    balance = 0
    end = 0
    for char in rest:
        if char == '(':
            balance += 1
        elif char == ')':
            if balance == 0:
                break
            balance -= 1
        end += 1

    if balance != 0:
        logging.critical(f"Error: parentheses are not balanced in {text}")
        return None

    logging.info(f"eval_and_patch_template_before_exec, {start}-{end} text: {text}\n")

    # adjust the end position relative to the original string
    end = end + start + prefix_len
    # evaluate the substring between @eval( and )
    expression = text[start+prefix_len:end].strip()
    try:
        evaluated = eval(expression)
    except Exception as e:
        logging.critical(f"Failed to evaluate {expression}. Error: {str(e)}")
        return None

    # replace the evaluated part in the original string
    text = text[:start] + str(evaluated) + text[end+1:]
    logging.info(f"text after patched: {text}\n")

    return text

def fix_string_to_json(s):
    # fix single quotes to double quotes
    s = s.replace("'", '"')
    return s