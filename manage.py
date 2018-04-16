#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
from app import create_app, db, scheduler
from app.models import User,Role
from flask_script import Manager,Shell
from flask_cors import *

app = create_app("dev")
CORS(app, supports_credentials=True)

manager = Manager(app, with_default_commands=False)

@manager.option('-c', '--config', dest='config', help='Configuration file name', default='scriptfan.cfg')
@manager.option('-H', '--host',   dest='host',   help='Host address', default='0.0.0.0')
@manager.option('-p', '--port',   dest='port',   help='Application port', default=5000)
def runserver(config, host, port):
    scheduler.start()
    app.run(host=host, port=port,debug=True)


def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role)


if __name__=="__main__":
    manager.run()