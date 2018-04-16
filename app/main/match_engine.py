from app import app, celery
from app.models import *


# 真实流水冲帐
def do_real_fund(contract, tplans, refund,commit_plan):
    # 逐期冲帐
    app.logger.info('使用真实还款流水[%s]开始冲账,余额:%s', refund.id, refund.remain_amt)

    #有减免时，先冲本金。这样，确保减免是发生在滞纳金上
    if commit_plan:
        for plan in tplans:
            balance_amount(plan, refund, contract)
        for plan in tplans:
            balance_fee(plan, refund, contract)
    else:
        for plan in tplans:
            balance_amount(plan, refund, contract)
            balance_fee(plan, refund, contract)


#冲本息
def balance_amount(plan,refund,contract):
    ac = plan.amt - plan.actual_amt  # 计算应冲值金额
    if ac > 0 and refund.remain_amt > 0:
        _b = min(refund.remain_amt, ac)  # 取最小值冲账
        plan.actual_amt += _b
        refund.remain_amt -= _b
        refund.contract_id = plan.contract_id
        plan.settled_date = refund.refund_time
        add_match_log(0, contract.id, plan.id, refund.id,
                      _b, refund.remain_amt,
                      plan.amt - plan.actual_amt,'本息冲账')
        app.logger.info('还款流水[%s]冲还款计划[%s]本息:%s,流水余额:%s,本息余额:%s',
                        refund.id, plan.id,
                        _b, refund.remain_amt,
                        plan.amt - plan.actual_amt)
#冲滞纳金
def balance_fee(plan,refund,contract):
    recount_fee(plan, refund, contract)  # 重新计算滞纳金
    fc = plan.fee - plan.actual_fee  # 计算应冲值金额
    if fc > 0 and refund.remain_amt > 0:
        _a = min(refund.remain_amt, fc)  # 取最小值冲账
        plan.actual_fee += _a
        refund.remain_amt -= _a
        refund.contract_id = plan.contract_id
        plan.settled_date = refund.refund_time
        add_match_log(1, contract.id, plan.id, refund.id,
                      _a, refund.remain_amt,
                      plan.fee - plan.actual_fee,'滞纳金冲账')
        app.logger.info('还款流水[%s]冲还款计划[%s]滞纳金:%s,流水余额:%s,滞纳金余额:%s',
                        refund.id, plan.id,
                        _a, refund.remain_amt,
                        plan.fee - plan.actual_fee)


# 重新计算滞纳金
def recount_fee(plan, refund, contract):
    (delayDay, fee) = get_fee(plan, refund, contract)
    if refund.remain_amt > 0 :
        if delayDay > 0 and delayDay != plan.delay_day:
            app.logger.info('还款流水[%s]因导入时间和实际还款时间的不一致，调整还款计划[%s]逾期天数:%s，滞纳金:%s,为逾期天数:%s，滞纳金:%s',
                            refund.id, plan.id, plan.delay_day, plan.fee, delayDay,fee)
            plan.fee = fee
            plan.delay_day = delayDay



# 获取最新的滞纳金
def get_fee(plan, refund, contract):
    delayDay = 0
    fee = 0
    if plan.actual_amt >= plan.amt:  # 仅对还清本息的还款计划有效
        delayDay = (refund.refund_time.date()-plan.deadline.date()).days  # 逾期天数
        if delayDay > 0:
            fee = countFee(contract.contract_amount, delayDay)
    return (delayDay, fee)


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


# 按照还款情况单笔冲账
def do_contract_refund(contract, tplans, refund=None, commit_plan=None):

    if refund and tplans:
        do_real_fund(contract, tplans, refund, commit_plan)

    # 结清状态计算
    v = 0
    if commit_plan:
        v += commit_plan.remain_amt
        app.logger.info('从减免计划[%s]获得减免额[%s]使用给贷款合同[%s]', commit_plan.id,commit_plan.remain_amt, contract.id)

    for plan in tplans:
        offV = plan.amt + plan.fee - plan.actual_amt - plan.actual_fee
        if v - offV >= 0:
            plan.is_settled = 1
            app.logger.info('还款计划[%s]已结清', plan.id)
            if commit_plan:
                commit_plan.remain_amt -= offV
                add_match_log(3, contract.id, plan.id, commit_plan.id,
                              offV, commit_plan.remain_amt,
                              0, '使用减免')
            v -= offV
        else:
            if commit_plan:
                if commit_plan.remain_amt>0:
                    commit_plan.remain_amt = 0
                    app.logger.warn('使用减免计划[%s]减免还款计划[%s]至少需要额度%s,额度不足', commit_plan.id,plan.id,offV)
            break

    # 同步合同状态
    if not get_refund_plan(contract.id, 0):
        contract.is_settled = 300  # 设置初始状态为结清
        app.logger.info('贷款合同[%s]已结清', contract.id)

    if contract.is_settled == 0 or contract.is_settled == 100:
        if get_refund_plan(contract.id, 1):
            contract.is_settled = 100  # 设置为逾期状态
        elif get_refund_plan(contract.id, 2):
            contract.is_settled = 0  # 设置初始状态为还款中

    db.session.commit()


# 获取未还清还款计划 0:全部 1:仅逾期 2:仅未到期
def get_refund_plan(contract_id, flag):
    tplans = ContractRepay.query.filter(ContractRepay.contract_id == contract_id,
                                     ContractRepay.is_settled == 0)

    if flag == 1:  # 逾期
        tplans = tplans.filter(ContractRepay.deadline < datetime.datetime.now())
    if flag == 2:  # 未到期
        tplans = tplans.filter(ContractRepay.deadline >= datetime.datetime.now())

    tplans = tplans.order_by(ContractRepay.deadline.asc()).all()
    return tplans

# 是否一次结清
def check_close(commit_plan):
    is_close = False
    if commit_plan:
        if commit_plan.discount_type == 1:  # 一次结清
            is_close = True
    return is_close


# 指定合同冲账 prePay:余额是否按照提前还款冲账
def match_by_contract(contract, refund=None, prePay=True):

    # 已结清的合同不应再重复处理
    if contract.is_settled == 300:
        app.logger.info('贷款合同[%s]已结清，略过', contract.id)
        return {'code': 5001, 'msg': '贷款合同[%s]已结清' % (contract.contract_no)}
    # 申请减免中的合同审批后再处理
    if check_exam_contract(contract):
        return {'code': 5002, 'msg': '贷款合同[%s]在申请减免中' % (contract.contract_no)}

    if refund:
        if refund.remain_amt <= 0:
            app.logger.info('还款流水[%s]余额不足:%s', refund.id, refund.remain_amt)
            return {'code': 5004, 'msg': '还款流水[%s]余额不足:%s' % (refund.id, refund.remain_amt)}

    commit_plan = get_reduce_plan(contract, refund)
    is_close = check_close(commit_plan)  # 是否一次结清

    if is_close:
        if not refund or refund.remain_amt > 0:
            plans = get_refund_plan(contract.id, 0)
            do_contract_refund(contract, plans, refund,commit_plan)
    else:
        # 优先处理逾期的计划
        if not refund or refund.remain_amt > 0:
            plans = get_refund_plan(contract.id, 1)
            do_contract_refund(contract, plans, refund,commit_plan)

        # 余额按照提前还款处理
        if prePay:
            if not refund or refund.remain_amt > 0:
                plans = get_refund_plan(contract.id, 2)
                do_contract_refund(contract, plans, refund,commit_plan)
    # 同步refund状态
    if refund:
        refund.t_status = 1 if refund.contract_id else 2


# 指定还款流水冲账
def match_by_refund(refund):
    # 根据姓名寻找待还款的合同
    # 移交外催的合同不自动处理，但可人工冲账
    contracts = Contract.query.filter(Contract.customer == refund.refund_name,
                                      Contract.is_settled < 300) \
                                        .order_by(Contract.loan_date.asc()).all()
    if contracts:
        id_no = contracts[0].id_number
        same_name_error = False
        for c in contracts:
            if id_no != c.id_number:  # 如果身份证号码不同，则确认为同名客户
                app.logger.warning('还款流水[%s] 发现同名客户的合同', refund.id)
                same_name_error = True
                break
        if same_name_error:
                return {'code': 5005, 'msg': '还款流水[%s] 发现同名客户的合同' % (refund.id)}
        else:
            app.logger.info('还款流水[%s]余额:%s开始冲账...', refund.id, refund.remain_amt)
            cl = len(contracts)
            # 如果是单笔合同,可提前还款
            if cl == 1:
                return match_by_contract(contracts[0], refund)

            elif cl > 1:
                # 如果是多笔合同，先处理每笔合同逾期情况，余额再作为提前还款
                if refund.remain_amt > 0:
                    # 先不要处理提前还款
                    for c in contracts:
                        r = match_by_contract(c, refund, False)
                        if r:
                            return r
                        if refund.remain_amt <= 0:
                            break
                if refund.remain_amt > 0:
                    # 如有余额再进行提前还款
                    for c in contracts:
                        r = match_by_contract(c, refund, True)
                        if r:
                            return r
                        if refund.remain_amt <= 0:
                            break
    else:
        app.logger.warning('还款流水[%s] 没有找到可冲账合同', refund.id)
        return {'code': 5006, 'msg': '还款流水[%s] 没有找到可冲账合同' % (refund.id)}



# 有无减免审批中的合同
def check_exam_contract(contract):
    commit_plan = CommitInfo.query.filter(CommitInfo.contract_id == contract.id,
                                          CommitInfo.type == 1,
                                          CommitInfo.result == 0
                                          ).all()
    return commit_plan

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

# 滞纳金算法
def countFee(contractAmt, delayDay):
    if contractAmt >= 10000 * 100:
        return delayDay * 200 * 100
    else:
        return delayDay * 100 * 100
