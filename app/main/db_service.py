import datetime

from sqlalchemy import func

from app import db, app
from app.main.utils import countFee, countDelayDay, MyExpection
from app.models import CommitInfo, ContractRepay, FundMatchLog, Contract, Repayment


# 获取有效减免审批建议
def get_reduce_plan(contract, refund):
    commit_plan = CommitInfo.query.filter(CommitInfo.contract_id == contract.id,
                                          CommitInfo.type == 1,
                                          CommitInfo.result == 100
                                          ).order_by(CommitInfo.apply_date.desc()).first()
    if commit_plan:
        # 如果存款时间在申请当天，审批额度则有效
        deadline_time = commit_plan.apply_date
        fund_time = refund.refund_time if refund else commit_plan.apply_date  # 如果是事后减免取申请时间
        if fund_time.date() == deadline_time.date() and commit_plan.remain_amt > 0:
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

# 删除合同
def do_del_contract(contract_id):
    result = db.session.query(FundMatchLog).filter(FundMatchLog.contract_id == contract_id, FundMatchLog.t_status == 0).all()
    if result:
        return {'isSucceed': 500, 'message': '发现已入账的数据'}
    else:
        contract = db.session.query(Contract).filter(Contract.id == contract_id).one()
        db.session.delete(contract)
        db.session.commit()
    return {'isSucceed': 200, 'message': ''}

# 重置还款流水
def do_refund_reset(refund_id):
    result = db.session.query(func.count(FundMatchLog.contract_id),FundMatchLog.contract_id)\
        .filter(FundMatchLog.fund_id == refund_id, FundMatchLog.t_status == 0)\
        .group_by(FundMatchLog.contract_id).all()
    if not result:
        return {'isSucceed': 500, 'message': '没发现冲账合同'}

    try:
        for (amt,contract_id) in result:
            do_refund_reset_by_contract(contract_id, refund_id)
    except MyExpection as e:
        db.session.rollback()
        return {'isSucceed': 500, 'message': e.message}

    db.session.commit()
    return {'isSucceed': 200, 'message': ''}

def do_refund_reset_by_contract(contract_id,refund_id):
    mlogs = db.session.query(FundMatchLog).filter(FundMatchLog.contract_id == contract_id, FundMatchLog.t_status == 0).order_by(FundMatchLog.id.desc()).all()

    if mlogs[0].fund_id != refund_id:
        raise MyExpection('非最后一笔冲账流水，请先重置最后一笔还款流水或取消减免计划【%s】' % (contract_id))

    contract = db.session.query(Contract).filter(Contract.id == contract_id).one()
    repayment = db.session.query(Repayment).filter(Repayment.id == refund_id).one()
    repayment.contract_id = None
    repayment.t_status = 2

    mlogs = db.session.query(FundMatchLog).filter(FundMatchLog.fund_id == refund_id, FundMatchLog.contract_id == contract_id, FundMatchLog.t_status == 0) \
        .order_by(FundMatchLog.created_time.desc()).all()

    for mlog in mlogs:
        if mlog.fund_id == refund_id:
            mlog.t_status = -1
            repayment.remain_amt += mlog.amount

            # 还款计划处理
            plan = db.session.query(ContractRepay).filter(ContractRepay.id == mlog.plan_id).one()
            plan.is_settled = 0
            if mlog.match_type == 0:  # 本息
                plan.actual_amt -= mlog.amount
                plan.settled_date = None
                recount_fee(plan, contract)  # 滞纳金重新计算
            elif mlog.match_type == 1:  # 滞纳金
                plan.actual_fee -= mlog.amount
        else:
            break
    syn_contract_status(contract)


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

    elif delay_day > 0:
        contract.delay_day = delay_day
        contract.repay_date = get_latest_repay_date(contract.id)
        contract.is_settled = 100  # 设置为逾期状态
    else:
        contract.delay_day = delay_day
        contract.repay_date = get_latest_repay_date(contract.id)
        contract.is_settled = 0  # 设置初始状态为还款中

# 计算未到期利息
def get_future_interest(contract, plans):
    future_interest = 0  # 未到期利息

    if contract.prepay_type == 0:
        principal = contract.contract_amount / contract.tensor
        skip_index = 1 if contract.repay_type == 1 else 0  # 后付费跳过2期
        today = datetime.date.today()
        i = 0  # 未到期计数器
        for plan in plans:
            # 当期利息正常计算
            if plan.deadline > today:
                if i > skip_index:
                    future_interest += (plan.amt - principal)
                i += 1
    return future_interest

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

# 重新计算滞纳金
def recount_fee(plan, contract):
    n_delay_day = countDelayDay(plan)  # 逾期天数
    if n_delay_day != plan.delay_day:
        fee = countFee(contract.contract_amount, n_delay_day)
        app.logger.info('调整还款计划[%s]逾期天数:%s，滞纳金:%s,为逾期天数:%s，滞纳金:%s',
                        plan.id, plan.delay_day, plan.fee, n_delay_day,fee)
        plan.fee = max(0, fee)  # 提前还款的直接归零
        plan.delay_day = max(0, n_delay_day)  # 提前还款的直接归零



