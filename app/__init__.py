from flask import Flask
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from config import config
from flask_login import LoginManager
from flask_mongoengine import MongoEngine
from celery import Celery
import pandas as pd
import redis,json,datetime,time
from pandas import DataFrame
from flask_apscheduler import APScheduler

app = Flask(__name__)

app.debug_log_format = '[%(levelname)s] %(message)s'
app.debug = True

app.config['CELERY_BROKER_URL'] = 'redis://127.0.0.1:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://127.0.0.1:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'], include=['app.tasks'])
celery.conf.update(app.config)



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
    from .main.table_data_server import count_daily_delay
    print("daily_quest_start %s"%(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    count_daily_delay()
    print('quest has done')


def create_app(config_name):
    app.logger.info('begin run application ...')

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

    return app
