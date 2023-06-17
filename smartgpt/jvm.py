import ast
import logging
import json
import os

# initialize a dictionary when the module is imported
kv_store_file = "kv_store.json"
kv_store = {}

def load_kv_store():
    global kv_store
    global kv_store_file
    # Load the kv_store dictionary from the file if it exists
    if os.path.exists(kv_store_file):
        with open(kv_store_file, 'r') as f:
            kv_store = json.load(f)

def get(key):
    load_kv_store()
    global kv_store
    
    try:
        value = kv_store.get(key, None)
        logging.info(f"get, key: {key}, value: {value}")
        if value is None:
            return None
        else:
            return value
    except Exception as e:
        logging.fatal(f"get, An error occurred: {e}")

def set(jarvis_key, value):
    load_kv_store()
    global kv_store
    global kv_store_file
    
    try:
        if isinstance(value, list):
            value = repr(value)
        logging.debug(f"set, jarvis_key: {jarvis_key}, value: {value}")
        kv_store[jarvis_key] = value

        # Save the kv_store dictionary to the file
        with open(kv_store_file, 'w') as f:
            json.dump(kv_store, f)
    except Exception as error:
        logging.fatal(f"set, An error occurred: {error}")

def all():
    load_kv_store()
    global kv_store
    try:
        kv_dict = {}
        for key, value in kv_store.items():
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            kv_dict[key] = value
        return kv_dict
    except Exception as e:
        logging.fatal(f"all, An error occurred: {e}")

def list_values_with_key_prefix(prefix):
    load_kv_store()
    global kv_store
    try:
        values = [value for key, value in kv_store.items() if key.startswith(prefix)]
        logging.info(f"list_values_with_key_prefix, prefix: {prefix}, values: {values}, len(values): {len(values)}")
        return values
    except Exception as e:
        logging.fatal(f"list_values_with_key_prefix, An error occurred: {e}")

def list_keys_with_prefix(prefix):
    load_kv_store()
    global kv_store
    try:
        keys = [key for key in kv_store.keys() if key.startswith(prefix)]
        return keys
    except Exception as e:
        logging.fatal(f"list_keys_with_prefix, An error occurred: {e}")

