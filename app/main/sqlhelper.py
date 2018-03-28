#!/usr/bin/python
# -*- coding: UTF-8 -*-

import MySQLdb,datetime
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


@SearchAll
def ontime_refund():
    now = datetime.datetime.now()
    start_time = now.replace(hour=0,minute=1,second=0)
    end_time = start_time+datetime.timedelta(days=1)
    sql = "SELECT * from t_refund_plan WHERE is_settled=0 and deadline BETWEEN %s and %s"
    param = (start_time,end_time)
    return sql,param

@SearchAll
def find_contractsby_id(contracts_id_list):
    sql='SELECT * from t_contract where id in %s'
    param = (contracts_id_list,)
    return sql,param

@Insert
def update_contract(is_dealt,is_settled,contract_id):
    sql = '''UPDATE t_contract set is_dealt = %s,is_settled = %s WHERE id=%s'''
    param = (is_dealt,is_settled,contract_id)
    return sql,param


@SearchAll
def ontime_commit():
    now = datetime.datetime.now()
    end_time = now.replace(hour=0,minute=0,second=0)+datetime.timedelta(days=1)
    sql="select * from t_commit_refund where is_valid=1 and is_settled=0 and deadline<=%s"
    param  = (end_time,)
    return sql,param

@Insert
def update_plan_by_commit(commit_id):
    sql='UPDATE t_refund_plan SET settled_by_commit = NULL where settled_by_commit = %s'
    param = (commit_id,)
    return sql,param

@Insert
def update_commit(is_valid,is_settled,result,commit_id):
    sql = 'UPDATE t_commit_refund SET is_valid = %s,is_settled=%s,result = %s WHERE id = %s'
    param = (is_valid,is_settled,result,commit_id)
    return sql,param

@Insert
def delete_contract_by_no(contract_nos):
    sql='DELETE From t_contract WHERE contract_no in %s'
    param = (contract_nos,)
    return sql,param


