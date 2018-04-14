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


#获取逾期记录
@SearchAll
def get_delay_refund():
    now = datetime.datetime.now()
    start_time = now.replace(hour=0,minute=1,second=0)
    #已还清本息的贷款不再计算滞纳金
    sql = "SELECT id,contract_id,deadline from t_refund_plan WHERE is_settled=0 and actual_amt >= amt and deadline < %s"
    param = (start_time,)
    return sql,param


#获取当日应还但未还的记录
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
    sql="select * from t_commit_refund where is_valid=0 and deadline<=%s"
    param  = (end_time,)
    return sql,param


@Insert
def update_plan_fee(fee,delay_day,id):
    sql='UPDATE t_refund_plan SET fee = %s,delay_day = %s where id = %s'
    param = (fee,delay_day,id)
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

#获取各门店最新支付时间和渠道
@SearchAll
def refund_newest_date():
    sql="SELECT MAX(r.refund_time) AS refund_time, IFNULL(r.bank, r.method) way, ct.shop AS shop FROM t_refund r LEFT JOIN t_contract ct ON r.contract_id = ct.id GROUP BY r.bank, r.method, ct.shop"
    param = ()
    return sql,param

#获取实际还款
@SearchAll
def get_real_pays(contract_id):
    sql="SELECT d.refund_time, d.refund_name, d.amount, IFNULL(d.bank, d.method) way FROM t_refund d WHERE d.contract_id = %s"
    param=(contract_id,)
    return sql,param

#获取拒绝原因
@Search
def get_refuse_reason(contract_id):
    sql="SELECT t.* FROM(SELECT cr.approve_remark,cr.result FROM t_commit_refund cr WHERE cr.contract_id = %s AND cr.result=0 ORDER BY cr.approve_date DESC) t LIMIT 1"
    param=(contract_id,)
    return sql,param
