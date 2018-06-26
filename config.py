#!/usr/bin/python
# -*- coding: UTF-8 -*-
import os
basedir=os.path.abspath(os.path.dirname(__file__))

class Config():
    SECRET_KEY=os.environ.get("SECRET_KEY") or "hard_to_guess_string"

    @staticmethod
    def init_app(app):
        pass



class DevConfig(Config):
    LOG_FILENAME = '/Users/newcity/PycharmProjects/webill-charge/celery.log'
    LOG_FILESIZE = 1024*1024*10 #10M

    UPLOAD_FOLD = '/Users/newcity/Uploads/'#上传文件目录
    DOWNLOAD_FOLD = "/Users/newcity/Uploads/"#下载模板目录
    TOKEN_TEST_URL = 'http://yadong.test.manmanh.com/webill-app/api/user/checkToken'#TOKEN验证api地址
    TOKEN_TEST_BUTTON = 0 # TOKEN验证开关
    DEBUG=False
    SQLALCHEMY_DATABASE_URI='mysql+pymysql://dev:devdb@192.168.98.133:3306/webill-test?charset=utf8'
    SQLALCHEMY_TRACK_MODIFICATIONS=True
    MONGODB_SETTINGS = {'db':'Datatable','alias':'default'}
    # MONGODB_SETTINGS = {'db':'Datatable','host': '192.168.98.133', 'port': 27017}

    CELERY_BROKER_URL = 'redis://mx_redis:6379/0'

    #celery 设置
    broker_url = 'redis://127.0.0.1:6379/0'
    result_backend = 'redis://127.0.0.1:6379/0'
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    #timezone = 'Europe/Oslo'
    enable_utc = True


    JOBS = [
        {
            'id': 'daily_quest',
            'func': 'app:daily_quest',
            'args': None,
            'trigger': {
                'type': 'cron',
                'day_of_week': "mon-sun",
                'hour': '19',
                'minute': '27',
                'second': '0'
            },
        }
    ]  # 跑批配置



config={
    "dev":DevConfig
}



