

runtime_env = {}


def get(key):
    global runtime_env
    return runtime_env.get(key)

def set(key, value):
    global runtime_env
    runtime_env[key] = value

def all():
    global runtime_env
    return runtime_env
