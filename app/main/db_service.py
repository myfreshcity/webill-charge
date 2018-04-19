import datetime

from flask import current_app

from app import db, app
from app.main.utils import countFee
from app.models import CommitInfo, ContractRepay, FundMatchLog, Contract


# 获取有效减免审批建议
def get_reduce_plan(contract, refund):
    commit_plan = CommitInfo.query.filter(CommitInfo.contract_id == contract.id,
                                          CommitInfo.type == 1,
                                          CommitInfo.result == 100
                                          ).order_by(CommitInfo.apply_date.desc()).first()
    if commit_plan:
        # 如果存款时间在申请当天，审批额度则有效
        deadline_time = commit_plan.apply_date.replace(hour=23, minute=59, second=59)
        fund_time = refund.refund_time if refund else commit_plan.apply_date  # 如果是事后减免取申请时间
        if fund_time < deadline_time and commit_plan.remain_amt > 0:
            return commit_plan
    else:
        return None

# 获取未还清还款计划 0:全部 1:仅逾期 2:仅未到期
def get_refund_plan(contract_id, flag):
    tplans = ContractRepay.query.filter(ContractRepay.is_settled == 0)

    if contract_id:
        tplans = tplans.filter(ContractRepay.contract_id == contract_id)

    now =  datetime.datetime.now()
    end_time = now.replace(hour=0, minute=0, second=0)

    if flag == 1:  # 逾期
        tplans = tplans.filter(ContractRepay.deadline < end_time)
    if flag == 2:  # 未到期
        tplans = tplans.filter(ContractRepay.deadline >= end_time)

    tplans = tplans.order_by(ContractRepay.deadline.asc()).all()
    return tplans

# 增加对账日志
def add_match_log(m_type,contract_id,plan_id,fund_id,amt=0,f_remain_amt=0,p_remain_amt=0,remark=None):
    log = FundMatchLog()
    log.match_type = m_type
    log.contract_id = contract_id
    log.fund_id = fund_id
    log.plan_id = plan_id
    log.amount = amt
    log.f_remain_amt = f_remain_amt
    log.p_remain_amt = p_remain_amt
    log.remark = remark
    db.session.add(log)

#计算每日逾期费用
def count_daily_delay():
    with app.app_context():
        plans = get_refund_plan(None,1)
        if plans:
            for plan in plans:
                contract_id = plan.contract_id
                contract = Contract.query.filter(Contract.id == contract_id).first()
                contractAmt = contract.contract_amount #合同额
                now = datetime.datetime.now()
                delayDay = (now.date()-plan.deadline.date()).days #逾期天数
                fee = countFee(contractAmt,delayDay)

                plan.fee = fee
                plan.delay_day = delayDay
                #update_contract(is_dealt=0,is_settled=0,contract_id=contract_id)
        db.session.commit()