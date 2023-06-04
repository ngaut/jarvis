
import sqlite3
import ast


# establish a connection when the module is imported
conn = sqlite3.connect('database.db')
cur = conn.cursor()

# create table if it doesn't exist
cur.execute('''CREATE TABLE IF NOT EXISTS kv_store
               (key TEXT PRIMARY KEY, value TEXT)''')

def get(key):
    try:
        cur.execute("SELECT value FROM kv_store WHERE key=?", (key,))
        value = cur.fetchone()
        if value is None:
            return None
        else:
            # Convert the value back to a list if it's a string representation of a list
            try:
                value = ast.literal_eval(value[0])
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            return value
    except Exception as e:
        print(f"An error occurred: {e}")


def set(key, value):
    try:
        # Convert the value to a string if it's a list
        if isinstance(value, list):
            value = str(value)
        cur.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")

def all():
    try:
        cur.execute("SELECT * FROM kv_store")
        kv_dict = {}
        for key, value in cur.fetchall():
            try:
                # Convert the value back to a list if it's a string representation of a list
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            kv_dict[key] = value
        return kv_dict
    except Exception as e:
        print(f"An error occurred: {e}")


# remember to close the connection when you're done
def close_db():
    conn.close()

# list_values_with_key_prefix
def list_values_with_key_prefix(prefix):
    try:
        cur.execute("SELECT value FROM kv_store WHERE key LIKE ?", (prefix + "%",))
        values = []
        for value, in cur.fetchall():
            try:
                # Convert the value back to a list if it's a string representation of a list
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # value is not a string representation of a list, so leave it as is
            values.append(value)
        return values
    except Exception as e:
        print(f"An error occurred: {e}")


# list_keys_with_prefix
def list_keys_with_prefix(prefix):
    try:
        cur.execute("SELECT key FROM kv_store WHERE key LIKE ?", (prefix + "%",))
        keys = [key for key, in cur.fetchall()]
        return keys
    except Exception as e:
        print(f"An error occurred: {e}")