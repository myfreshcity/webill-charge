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
    UPLOAD_FOLD = 'F://upload/'#上传文件存放目录
    DOWNLOAD_FOLD = "F://download"#下载文件存放目录
    TOKEN_TEST_URL = 'http://yadong.test.manmanh.com/webill-app/api/user/checkToken'#Token检验URL
    TOKEN_TEST_BUTTON = 0#Token验证是否开启，0关闭，1开启
    SQLHELPER={'host':'192.168.99.152','username':'root','passwd':'root','db':'consumerfin11','port':3306}#sqlhelper的数据库配置
    DEBUG=False
    SQLALCHEMY_DATABASE_URI='mysql+pymysql://root:zx1994617@127.0.0.1:3306/testsql?charset=utf8'#sqlalchemy的数据库配置
    SQLALCHEMY_TRACK_MODIFICATIONS=True
    MONGODB_SETTINGS = {'db':'Datatable','alias':'default'}#mongoengine的数据库配置
    # MONGODB_SETTINGS = {'db':'Datatable','host': '192.168.98.133', 'port': 27017}



config={
    "dev":DevConfig
}



