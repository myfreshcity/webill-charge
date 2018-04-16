import os, sys
import os,http
import requests
from flask import Flask, render_template, abort, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_script import Manager, Shell
from app import create_app,db
from app.main.sqlhelper import *
from app.models import *
from app.main.match_engine import *
from app.main.table_data_server import *


app=create_app("dev")
manager=Manager(app)

app.log_format = '%(asctime)s %(funcName)s [%(levelname)s] %(message)s'
app.debug = True

ctx = app.app_context()
ctx.push()

from sqlalchemy.ext.declarative import DeclarativeMeta
import json
class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data) # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        return json.JSONEncoder.default(self, obj)


def main():

    # 准备环境
    # set_cond_001()  # 单期逾期
    # set_cond_002()  # 多期逾期

    #reduce_001()  # 清欠
    # reduce_002()  # 结清
    #db.session.commit()

    # 对账设置
    # repayment_001()  # 导入冲账
    # repayment_002()  # 指定冲账
    #repayment_003()  # 还款后冲账

    query_info()



#导入冲账
def repayment_001():
    refund = Repayment.query.filter(Repayment.id == '103').first()
    refund.remain_amt = 5000
    refund.refund_time = datetime.datetime.now() - datetime.timedelta(days=1)
    result = match_by_refund(refund)
    app.logger.warning(result)


#指定流水冲账
def repayment_002():
    refund = Repayment.query.filter(Repayment.id == '104').first()
    refund.remain_amt = 5000
    refund.refund_time = datetime.datetime.now() - datetime.timedelta(days=1)
    contract = Contract.query.filter(Contract.id == '25').first()
    result = match_by_contract(contract,refund)
    app.logger.warning(result)


#还款后减免
def repayment_003():
    contract = Contract.query.filter(Contract.id == '25').first()
    result = match_by_contract(contract)
    app.logger.warning(result)



#单期逾期
def set_cond_001():
    contract = Contract.query.filter(Contract.id == '25').first()
    plan = RefundPlan.query.filter(RefundPlan.id == '49').first()
    plan2 = RefundPlan.query.filter(RefundPlan.id == '50').first()
    plan3 = RefundPlan.query.filter(RefundPlan.id == '51').first()

    # 重置合同状态
    contract.is_settled = 0
    # 重置还款计划
    plan.is_settled = 0
    plan2.is_settled = 0
    plan3.is_settled = 0

    plan.deadline = datetime.datetime.now() - datetime.timedelta(days=4)
    plan.amt = 5000
    plan.fee = 40000
    plan.delay_day = 4
    plan.actual_amt = 0
    plan.actual_fee = 0

    plan2.deadline = datetime.datetime.now() + datetime.timedelta(days=7)
    plan2.amt = 5000
    plan2.fee = 0
    plan2.delay_day = 0
    plan2.actual_amt = 0
    plan2.actual_fee = 0

    plan3.deadline = datetime.datetime.now() + datetime.timedelta(days=14)
    plan3.amt = 5000
    plan3.fee = 0
    plan3.delay_day = 0
    plan3.actual_amt = 0
    plan3.actual_fee = 0


# 多期逾期包含减免
def set_cond_002():
    contract = Contract.query.filter(Contract.id == '25').first()
    plan = RefundPlan.query.filter(RefundPlan.id == '49').first()
    plan2 = RefundPlan.query.filter(RefundPlan.id == '50').first()
    plan3 = RefundPlan.query.filter(RefundPlan.id == '51').first()

    # 重置合同状态
    contract.is_settled = 0
    # 重置还款计划
    plan.is_settled = 0
    plan2.is_settled = 0
    plan3.is_settled = 0

    plan.deadline = datetime.datetime.now() - datetime.timedelta(days=4)
    plan.amt = 5000
    plan.fee = 40000
    plan.delay_day = 4
    plan.actual_amt = 0
    plan.actual_fee = 0

    plan2.deadline = datetime.datetime.now() - datetime.timedelta(days=2)
    plan2.amt = 5000
    plan2.fee = 20000
    plan2.delay_day = 2
    plan2.actual_amt = 0
    plan2.actual_fee = 0

    plan3.deadline = datetime.datetime.now() + datetime.timedelta(days=2)
    plan3.amt = 5000
    plan3.fee = 0
    plan3.delay_day = 0
    plan3.actual_amt = 0
    plan3.actual_fee = 0

# 清欠
def reduce_001():
    cRefund = CommitRefund.query.filter(CommitRefund.id == '21').first()
    cRefund.remain_amt = 22000
    cRefund.discount_type = 0
    cRefund.apply_date = datetime.datetime.now()

#结清
def reduce_002():
    cRefund = CommitRefund.query.filter(CommitRefund.id == '21').first()
    cRefund.remain_amt = 12000
    cRefund.discount_type = 1
    cRefund.apply_date = datetime.datetime.now()



def query_info():
    contract = Contract.query.filter(Contract.id == '25').first()
    plan = RefundPlan.query.filter(RefundPlan.id == '49').first()
    plan2 = RefundPlan.query.filter(RefundPlan.id == '50').first()
    plan3 = RefundPlan.query.filter(RefundPlan.id == '51').first()
    refund = Repayment.query.filter(Repayment.id == '103').first()

    #app.logger.info('contract:%s',json.dumps(contract, cls=AlchemyEncoder))
    app.logger.info('contract:%s', contract.is_settled)
    app.logger.info('plan:%s',json.dumps(plan, cls=AlchemyEncoder))
    app.logger.info('plan2:%s',json.dumps(plan2, cls=AlchemyEncoder))
    app.logger.info('plan3:%s',json.dumps(plan3, cls=AlchemyEncoder))
    app.logger.info('refund:%s',json.dumps(refund, cls=AlchemyEncoder))



if __name__=="__main__":
    main()