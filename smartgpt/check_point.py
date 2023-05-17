# check_point.py
import datetime
import logging
from peewee import Model, TextField, DateTimeField, MySQLDatabase
from playhouse.shortcuts import model_to_dict
from peewee import DoesNotExist


class Checkpoint(Model):
    goal = TextField(index=True)
    task_description = TextField(index=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    # The Meta class is now empty, we will set the database later
    class Meta:
        pass

class CheckpointDatabase:
    def __init__(self, db_name, db_user, db_password, db_host, db_port, ssl):
        self.db = MySQLDatabase(db_name, user=db_user, password=db_password, host=db_host, port=db_port, ssl=ssl)
        # Assign the database to the Checkpoint model
        Checkpoint._meta.database = self.db

    def create_table(self):
        self.db.connect()
        self.db.create_tables([Checkpoint])

    def save_checkpoint(self, task_description: str, goal:str):
        try:
            checkpoint = Checkpoint(task_description=task_description, goal=goal)
            checkpoint.save()
        except Exception as e:
            logging.info(f"An error occurred while trying to save a checkpoint: {e}")
            # Consider re-raising the exception or handle it in a way that makes sense for your application
            # raise e

    def load_checkpoint(self, task_description: str = None):
        try:
            if task_description:
                checkpoint = Checkpoint.select().where(Checkpoint.task_description == task_description).order_by(Checkpoint.created_at.desc()).get()
            else:
                checkpoint = Checkpoint.select().order_by(Checkpoint.created_at.desc()).get()

            return model_to_dict(checkpoint)
        except DoesNotExist:
            return None  # or handle in another way that makes sense for your application
        except Exception as e:
            logging.info(f"An error occurred while trying to load a checkpoint: {e}")
            # Consider re-raising the exception or handle it in a way that makes sense for your application
            # raise e


