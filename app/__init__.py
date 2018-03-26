from flask import Flask
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from config import config
from flask_login import LoginManager
from flask_mongoengine import MongoEngine
import pandas as pd
import redis,json,datetime,time
from pandas import DataFrame
from flask_apscheduler import APScheduler


bootstrap=Bootstrap()
moment=Moment()
db=SQLAlchemy()
login_manager=LoginManager()
mdb = MongoEngine()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'
pool = redis.ConnectionPool(host='127.0.0.1', port=6379, db=0)
red = redis.StrictRedis(connection_pool=pool)
scheduler = APScheduler()

def daily_quest():
    from .main.table_data_server import ontime_refunds,ontime_commits
    print("daily_quest_start %s"%(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    ontime_refunds()
    ontime_commits()
    print('quest has done')


def create_app(config_name):
    app=Flask(__name__)

    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    bootstrap.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    mdb.init_app(app)
    scheduler.init_app(app)

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint,url_prefix='/auth')

    scheduler.start()

    return app
