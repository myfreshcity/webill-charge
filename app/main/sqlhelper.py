#!/usr/bin/python
# -*- coding: UTF-8 -*-

import MySQLdb
import MySQLdb.cursors

def get_conn():
    from .. import config
    mysqlconfig = config['dev'].SQLHELPER
    host = mysqlconfig['host']
    username = mysqlconfig['username']
    passwd = mysqlconfig['passwd']
    db = mysqlconfig['db']
    port=mysqlconfig['port']
    conn=MySQLdb.connect(host=host,port=port,user=username,passwd=passwd,db=db,charset='utf8',cursorclass=MySQLdb.cursors.DictCursor)
    return conn

#信息查询装饰函数(单个)
def Search(func):
    def out(*args,**kwargs):
        conn = get_conn()
        cursor = conn.cursor()
        sql,parama = func(*args,**kwargs)
        cursor.execute(sql, parama)
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        return data
    return out

#信息查询装饰函数（全部）
def SearchAll(func):
    def out(*args,**kwargs):
        conn = get_conn()
        cursor = conn.cursor()
        sql,parama = func(*args,**kwargs)
        cursor.execute(sql, parama)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    return out

#信息插入装饰器
def Insert(func):
    def out(*args,**kwargs):
        conn = get_conn()
        cursor = conn.cursor()
        sql,parama = func(*args,**kwargs)
        cursor.execute(sql, parama)
        conn.commit()
        cursor.close()
        conn.close()
    return out


