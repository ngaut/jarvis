import datetime
from peewee import Model, TextField, DateTimeField, MySQLDatabase
from playhouse.shortcuts import model_to_dict
from playhouse.mysql_ext import JSONField

db = MySQLDatabase(
    'jarvis',  # your_database_name
    user='2bw9XzdKWiSnJgo.root',  # your_username
    password='GAVkkA9tDiGEtV0Q',  # your_password
    host='gateway01.ap-southeast-1.prod.aws.tidbcloud.com',  # your_host
    port=4000,  # your_port
    ssl = {
    'ca': '/etc/ssl/cert.pem',
    'ssl_mode': "VERIFY_IDENTITY"
    }
)


class Checkpoint(Model):
    task_description = TextField(index=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        database = db

def create_table():
    db.connect()
    db.create_tables([Checkpoint])

def save_checkpoint(task_description: str):
    checkpoint = Checkpoint(task_description=task_description)
    checkpoint.save()

def load_checkpoint(task_description: str = None):
    if task_description:
        checkpoint = Checkpoint.select().where(Checkpoint.task_description == task_description).order_by(Checkpoint.created_at.desc()).get()
    else:
        checkpoint = Checkpoint.select().order_by(Checkpoint.created_at.desc()).get()
    
    return model_to_dict(checkpoint)