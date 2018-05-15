from app import app
from app.main.db_service import get_reduce_plan, get_refund_plan, add_match_log, get_latest_repay_date, \
    syn_contract_status
from app.main.utils import countFee, countDelayDay, MyExpection, date2datetime
from app.models import *


# 真实流水冲帐
def do_real_fund(contract, tplans, refund,commit_plan):
    # 逐期冲帐
    app.logger.info('使用真实还款流水[%s]开始冲账,余额:%s', refund.id, refund.remain_amt)

    #如果为多期时，先冲本息
    if len(tplans) > 1:
        for plan in tplans:
            balance_amount(plan, refund, contract)
        for plan in tplans:
            balance_fee(plan, refund, contract)
    else:
        plan = tplans[0]
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
        #plan.settled_date = refund.refund_time
        add_match_log(1, contract.id, plan.id, refund.id,
                      _a, refund.remain_amt,
                      plan.fee - plan.actual_fee,'滞纳金冲账')
        app.logger.info('还款流水[%s]冲还款计划[%s]滞纳金:%s,流水余额:%s,滞纳金余额:%s',
                        refund.id, plan.id,
                        _a, refund.remain_amt,
                        plan.fee - plan.actual_fee)


# 重新计算滞纳金
def recount_fee(plan, refund, contract):
    if plan.actual_amt >= plan.amt:  # 仅对还清本息的还款计划有效
        n_delay_day = countDelayDay(plan)  # 逾期天数
        if n_delay_day != plan.delay_day:
            fee = countFee(contract.contract_amount, n_delay_day)
            app.logger.info('还款流水[%s]因导入时间和实际还款时间的不一致，调整还款计划[%s]逾期天数:%s，滞纳金:%s,为逾期天数:%s，滞纳金:%s',
                            refund.id, plan.id, plan.delay_day, plan.fee, n_delay_day,fee)
            plan.fee = max(0, fee)  # 提前还款的直接归零
            plan.delay_day = max(0, n_delay_day)  # 提前还款的直接归零


def do_check_commit_amt(reduce_amt, tplans):
    i = 0
    for plan in tplans:
        offV = plan.amt + plan.fee - plan.actual_amt - plan.actual_fee
        i += offV
    if reduce_amt >= i:
        return True
    else:
        app.logger.info('减免额度不足，至少需要[%s]', i)
        raise MyExpection('减免额度不足，至少需要[%s]' % int(i/100))


# 按照还款情况单笔冲账
def do_contract_refund(contract, tplans, refund=None, commit_plan=None):

    if refund and tplans:
        do_real_fund(contract, tplans, refund, commit_plan)

    # 结清状态计算
    v = 0
    flag = True
    if commit_plan:
        v += commit_plan.remain_amt
        app.logger.info('从减免计划[%s]获得减免额[%s]使用给贷款合同[%s]', commit_plan.id,commit_plan.remain_amt, contract.id)
        flag = do_check_commit_amt(v, tplans)  # 减免额是否足够

    if flag:
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
    syn_contract_status(contract)


# 是否一次结清
def check_close(commit_plan):
    is_close = False
    if commit_plan:
        if commit_plan.discount_type == 1:  # 一次结清
            is_close = True
    return is_close


# 指定合同冲账
def match_by_contract(contract, refund=None):
    app.logger.info('---合同[%s] 冲账开始---', contract.id)
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
            return {'code': 5004, 'msg': '还款流水[%s]余额不足:%s' % (refund.id, int(refund.remain_amt/100))}
        if refund.refund_time < date2datetime(contract.loan_date):
            return {'code': 5004, 'msg': '还款流水[%s]支付时间早于合同放款时间' % (refund.id)}

    commit_plan = get_reduce_plan(contract, refund)
    is_close = check_close(commit_plan)  # 是否一次结清

    if is_close:
        plans = get_refund_plan(contract.id)
    else:
        # 先按照逾期还款，否则按照提前还款
        plans = get_refund_plan(contract.id, 1, refund)
        if not plans:
            plans = get_refund_plan(contract.id, 2, refund)

    try:
        do_contract_refund(contract, plans, refund, commit_plan)
    except MyExpection as e:
        db.session.rollback()
        return {'code': 5004, 'msg': e.message}

    # 同步refund状态
    if refund:
        refund.t_status = 1 if refund.contract_id else 2

    db.session.commit()
    app.logger.info('---合同[%s] 冲账结束---', contract.id)

# 指定还款流水冲账
def match_by_refund(refund):
    app.logger.info('---还款流水[%s] 冲账开始---', refund.id)
    # 初始化流水状态
    refund.t_status = 2
    db.session.commit()
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
            # 如果是单笔合同
            if cl == 1:
                return match_by_contract(contracts[0], refund)

            elif cl > 1:
                # 如果是多笔合同，先按照逾期情况处理
                if refund.remain_amt > 0:
                    # 先不要处理提前还款
                    for c in contracts:
                        r = match_by_contract(c, refund)
                        if r:
                            return r
                        if refund.remain_amt <= 0:
                            break

    else:
        app.logger.warning('还款流水[%s] 没有找到可冲账合同', refund.id)
        return {'code': 5006, 'msg': '还款流水[%s] 没有找到可冲账合同' % (refund.id)}

    app.logger.info('---还款流水[%s] 冲账结束---', refund.id)



# 有无减免审批中的合同
def check_exam_contract(contract):
    commit_plan = CommitInfo.query.filter(CommitInfo.contract_id == contract.id,
                                          CommitInfo.type == 1,
                                          CommitInfo.result == 0
                                          ).all()
    return commit_plan





