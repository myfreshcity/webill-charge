import flask, logging
from flask import Flask, current_app
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

#app.config['CELERY_BROKER_URL'] = 'redis://127.0.0.1:6379/0'
#app.config['CELERY_RESULT_BACKEND'] = 'redis://127.0.0.1:6379/0'


class FlaskCelery(Celery):
    def __init__(self, *args, **kwargs):
        super(FlaskCelery, self).__init__(*args, **kwargs)
        self.patch_task()

        if 'app' in kwargs:
            self.init_app(kwargs['app'])

    def patch_task(self):
        TaskBase = self.Task
        _celery = self

        class ContextTask(TaskBase):
            abstract = True

            def __call__(self, *args, **kwargs):
                if flask.has_app_context():
                    return TaskBase.__call__(self, *args, **kwargs)
                else:
                    with _celery.app.app_context():
                        return TaskBase.__call__(self, *args, **kwargs)

        self.Task = ContextTask

    def init_app(self, app):
        self.app = app
        self.config_from_object(app.config)

app.config.from_object(config['dev'])
celery = FlaskCelery(app.name, broker=app.config['CELERY_BROKER_URL'], include=['app.tasks'])
celery.init_app(app)

bootstrap=Bootstrap()
moment=Moment()
db=SQLAlchemy()
db.init_app(app)

login_manager=LoginManager()
mdb = MongoEngine()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'
pool = redis.ConnectionPool(host='127.0.0.1', port=6379, db=0)
red = redis.StrictRedis(connection_pool=pool)
scheduler = APScheduler()

def daily_quest():
    from .main.db_service import count_daily_delay
    print("daily_quest_start %s"%(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    count_daily_delay()
    print('quest has done')


def create_app(configName=None):
    handler = logging.handlers.RotatingFileHandler(app.config.get('LOG_FILENAME'),
                                                   maxBytes=app.config.get('LOG_FILESIZE'),
                                                   backupCount=20, encoding='UTF-8')
    handler.setLevel(logging.DEBUG)
    logging_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s - %(lineno)s - %(message)s')
    handler.setFormatter(logging_format)
    app.logger.addHandler(handler)

    app.logger.info('begin run application ...')

    bootstrap.init_app(app)
    moment.init_app(app)
    login_manager.init_app(app)
    mdb.init_app(app)
    scheduler.init_app(app)
    return app

def register_blueprints(app):
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')


