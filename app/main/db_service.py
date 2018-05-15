import datetime

from flask import current_app
from sqlalchemy import func

from app import db, app
from app.main.utils import countFee, countDelayDay
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
def get_refund_plan(contract_id, flag=0, refund=None):
    tplans = ContractRepay.query.filter(ContractRepay.is_settled == 0,ContractRepay.contract_id == contract_id)

    if refund:
        end_time = refund.refund_time
    else:
        end_time =  datetime.datetime.now()

    end_time = end_time.date()

    if flag == 1:  # 逾期(包含当期)
        tplans = tplans.filter(ContractRepay.deadline <= end_time)
    if flag == 2:  # 未到期(包含当期)
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

# 最近还款日期
def get_latest_repay_date(contract_id):
    dt = db.session.query(func.min(ContractRepay.deadline))\
        .filter(ContractRepay.contract_id == contract_id,ContractRepay.actual_amt < ContractRepay.amt)\
        .scalar()
    return dt

# 同步合同状态
def syn_contract_status(contract):
    from sqlalchemy import func
    delay_day = db.session.query(func.max(ContractRepay.delay_day)).filter(ContractRepay.contract_id == contract.id,
                                                                           ContractRepay.is_settled == 0).scalar()

    if delay_day is None:
        contract.delay_day = 0
        contract.is_settled = 300  # 设置初始状态为结清
        contract.repay_date = None
        app.logger.info('贷款合同[%s]已结清', contract.id)

    if contract.is_settled == 0 or contract.is_settled == 100:
        if delay_day > 0:
            contract.delay_day = delay_day
            contract.repay_date = get_latest_repay_date(contract.id)
            contract.is_settled = 100  # 设置为逾期状态
        else:
            contract.delay_day = delay_day
            contract.repay_date = get_latest_repay_date(contract.id)
            contract.is_settled = 0  # 设置初始状态为还款中


# 计算每日逾期费用
def count_daily_delay():
    with app.app_context():
        app.logger.info('---每日逾期费用计算开始---')

        plans = ContractRepay.query.filter(ContractRepay.is_settled == 0)\
            .filter(ContractRepay.deadline < datetime.date.today())\
            .order_by(ContractRepay.deadline.asc()).all()

        if plans:
            for plan in plans:
                contract_id = plan.contract_id
                contract = Contract.query.filter(Contract.id == contract_id).first()
                contractAmt = contract.contract_amount  # 合同额
                delayDay = countDelayDay(plan)  # 逾期天数
                fee = countFee(contractAmt, delayDay)

                plan.fee = fee
                plan.delay_day = delayDay
                syn_contract_status(contract)

                app.logger.info('---还款计划[%s] 计算结束---', plan.id)
        db.session.commit()