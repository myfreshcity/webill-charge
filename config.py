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
    UPLOAD_FOLD = 'F://upload/'#上传文件目录
    DOWNLOAD_FOLD = "F://download"#下载模板目录
    TOKEN_TEST_URL = 'http://yadong.test.manmanh.com/webill-app/api/user/checkToken'#TOKEN验证api地址
    TOKEN_TEST_BUTTON = 0#TOKEN验证开关
    SQLHELPER={'host':'127.0.0.1','username':'root','passwd':'zx1994617','db':'testsql','port':3306}
    DEBUG=False
    SQLALCHEMY_DATABASE_URI='mysql+pymysql://root:zx1994617@127.0.0.1:3306/testsql?charset=utf8'
    SQLALCHEMY_TRACK_MODIFICATIONS=True
    MONGODB_SETTINGS = {'db':'Datatable','alias':'default'}
    # MONGODB_SETTINGS = {'db':'Datatable','host': '192.168.98.133', 'port': 27017}
    JOBS = [
        {
            'id': 'daily_quest',
            'func': 'app:daily_quest',
            'args': None,
            'trigger': {
                'type': 'cron',
                'day_of_week': "mon-sun",
                'hour': '14',
                'minute': '09',
                'second': '0'
            },
        }
    ]  # 跑批配置



config={
    "dev":DevConfig
}



