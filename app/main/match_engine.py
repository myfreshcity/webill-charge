import math

from app import app
from app.main.db_service import get_reduce_plan, get_refund_plan, get_future_interest, add_match_log, recount_fee, \
    syn_contract_status
from app.main.utils import MyExpection, date2datetime
from app.models import *


class MatchEngine:
    def __init__(self):
        self.refund = None
        self.contract = None
        self.commit_plan = None
        self.fee_first = False  # 滞纳金优先
        self.amount = 0  # 冲账金额

    # 真实流水冲帐
    def __do_real_fund(self,tplans):
        # 逐期冲帐
        app.logger.info('使用真实还款流水[%s]开始冲账,余额:%s,冲账金额%s', self.refund.id, self.refund.remain_amt,self.amount)
        amount = self.amount

        #如果为多期时，先冲本息
        if len(tplans) > 1 and (not self.fee_first):
            for plan in tplans:
                self.__balance_amount(plan)
            for plan in tplans:
                self.__balance_fee(plan)
        else:
            plan = tplans[0]
            self.__balance_amount(plan)
            self.__balance_fee(plan)

        # 同步资金余额
        self.refund.remain_amt = self.refund.remain_amt - (amount - self.amount)


    #冲本息
    def __balance_amount(self,plan):
        ac = plan.amt - plan.actual_amt  # 计算应冲值金额
        if ac > 0 and self.amount > 0:
            _b = min(self.amount, ac)  # 取最小值冲账
            plan.actual_amt += _b
            self.amount -= _b
            self.refund.contract_id = plan.contract_id
            if plan.actual_amt >= plan.amt:
                plan.settled_date = self.refund.refund_time
            add_match_log(0, self.contract.id, plan.id, self.refund.id,
                          _b, self.amount,
                          plan.amt - plan.actual_amt,'本息冲账')
            app.logger.info('还款流水[%s]冲还款计划[%s]本息:%s,流水余额:%s,本息余额:%s',
                            self.refund.id, plan.id,
                            _b, self.amount,
                            plan.amt - plan.actual_amt)
    #冲滞纳金
    def __balance_fee(self,plan):
        recount_fee(plan, self.contract)  # 重新计算滞纳金
        fc = plan.fee - plan.actual_fee  # 计算应冲值金额
        if fc > 0 and self.amount > 0:
            _a = min(self.amount, fc)  # 取最小值冲账
            plan.actual_fee += _a
            self.amount -= _a
            self.refund.contract_id = plan.contract_id
            #plan.settled_date = self.refund.refund_time
            add_match_log(1, self.contract.id, plan.id, self.refund.id,
                          _a, self.amount,
                          plan.fee - plan.actual_fee,'滞纳金冲账')
            app.logger.info('还款流水[%s]冲还款计划[%s]滞纳金:%s,流水余额:%s,滞纳金余额:%s',
                            self.refund.id, plan.id,
                            _a, self.amount,
                            plan.fee - plan.actual_fee)


    def __do_check_commit_amt(self,reduce_amt,fit, tplans):
        i = 0
        for plan in tplans:
            offV = plan.amt + plan.fee - plan.actual_amt - plan.actual_fee
            i += offV
        if reduce_amt+fit >= i:
            self.commit_plan.remain_amt = 0
            return True
        else:
            app.logger.info('减免额度不足，至少需要[%s]', i-fit)
            raise MyExpection('减免额度不足，至少需要[%s]' % math.ceil((i-fit) / 100))


    # 按照还款情况单笔冲账
    def __do_contract_refund(self,tplans):

        if self.refund and tplans:
            self.__do_real_fund(tplans)

        # 结清状态计算
        v = 0
        fit = get_future_interest(self.contract, tplans) # 未到期利息
        flag = True
        if self.commit_plan:
            v += self.commit_plan.remain_amt
            app.logger.info('从减免计划[%s]获得减免额[%s]使用给贷款合同[%s]', self.commit_plan.id,self.commit_plan.remain_amt, self.contract.id)
            flag = self.__do_check_commit_amt(v,fit, tplans)  # 减免额是否足够

        if flag:
            v = v + fit
            for plan in tplans:
                offV = plan.amt + plan.fee - plan.actual_amt - plan.actual_fee
                if v - offV >= 0:
                    plan.is_settled = 1
                    app.logger.info('还款计划[%s]已结清', plan.id)
                    if self.commit_plan:
                        rfid = self.refund.id if self.refund else None
                        add_match_log(3, self.contract.id, plan.id, rfid,0, 0,0, '使用减免:%s' % (self.commit_plan.id))
                v -= offV

        # 同步合同状态
        syn_contract_status(self.contract)


    # 是否一次结清
    def __check_close(self):
        is_close = False
        if self.commit_plan:
            if self.commit_plan.discount_type > 0:  # 结清
                is_close = True
        return is_close


    # 指定合同冲账
    def match_by_contract(self, contract, refund=None, fee_first=False, amount=0):
        self.contract = contract
        self.fee_first = fee_first
        self.amount = amount
        self.refund = refund

        app.logger.info('---合同[%s] 冲账开始---', self.contract.id)
        # 已结清的合同不应再重复处理
        if self.contract.is_settled == 300:
            app.logger.info('贷款合同[%s]已结清，略过', self.contract.id)
            return {'code': 5001, 'msg': '贷款合同[%s]已结清' % (self.contract.contract_no)}
        # 申请减免中的合同审批后再处理
        if self.__check_exam_contract():
            return {'code': 5002, 'msg': '贷款合同[%s]在申请减免中' % (self.contract.contract_no)}

        if self.refund:
            if self.refund.remain_amt <= 0:
                app.logger.info('还款流水[%s]余额不足:%s', self.refund.id, self.refund.remain_amt)
                return {'code': 5004, 'msg': '还款流水[%s]余额不足:%s' % (self.refund.id, int(self.refund.remain_amt/100))}
            if self.refund.refund_time < date2datetime(self.contract.loan_date):
                return {'code': 5004, 'msg': '还款流水[%s]支付时间早于合同放款时间' % (self.refund.id)}
            if self.amount > self.refund.remain_amt:
                return {'code': 5004, 'msg': '冲账金额应小于还款流水[%s]余额:%s' % (self.refund.id, int(self.refund.remain_amt / 100))}

        self.commit_plan = get_reduce_plan(self.contract,self.refund)
        is_close = self.__check_close()  # 是否一次结清

        if is_close:
            plans = get_refund_plan(self.contract.id)
        else:
            # 先按照逾期还款，否则按照提前还款
            plans = get_refund_plan(self.contract.id, 1, self.refund)
            if not plans:
                plans = get_refund_plan(self.contract.id, 2, self.refund)

        try:
            self.__do_contract_refund(plans)
        except MyExpection as e:
            db.session.rollback()
            return {'code': 5004, 'msg': e.message}

        # 同步refund状态
        if self.refund:
            self.refund.t_status = 1 if self.refund.contract_id else 2

        db.session.commit()
        app.logger.info('---合同[%s] 冲账结束---', self.contract.id)

    # 指定还款流水冲账
    def match_by_refund(self, refund):
        self.refund = refund
        app.logger.info('---还款流水[%s] 冲账开始---', self.refund.id)
        # 初始化流水状态
        self.refund.t_status = 2
        db.session.commit()
        # 根据姓名寻找待还款的合同
        # 移交外催的合同不自动处理，但可人工冲账
        contracts = Contract.query.filter(Contract.customer == self.refund.refund_name,
                                          Contract.shop == self.refund.shop,
                                          Contract.is_settled < 300) \
                                            .order_by(Contract.loan_date.asc()).all()
        if contracts:
            id_no = contracts[0].id_number
            same_name_error = False
            for c in contracts:
                if id_no != c.id_number:  # 如果身份证号码不同，则确认为同名客户
                    app.logger.warning('还款流水[%s] 发现同名客户的合同', self.refund.id)
                    same_name_error = True
                    break
            if same_name_error:
                    return {'code': 5005, 'msg': '还款流水[%s] 发现同名客户的合同' % (self.refund.id)}
            else:
                app.logger.info('还款流水[%s]余额:%s开始冲账...', self.refund.id, self.refund.remain_amt)
                cl = len(contracts)
                # 如果是单笔合同
                if cl == 1:
                    return self.match_by_contract(contracts[0],self.refund,False,self.refund.remain_amt)

                elif cl > 1:
                    # 如果是多笔合同，先按照逾期情况处理
                    if self.refund.remain_amt > 0:
                        # 先不要处理提前还款
                        for c in contracts:
                            r = self.match_by_contract(c,self.refund,False,self.refund.remain_amt)
                            if r:
                                return r
                            if self.refund.remain_amt <= 0:
                                break

        else:
            app.logger.warning('还款流水[%s] 没有找到可冲账合同', self.refund.id)
            return {'code': 5006, 'msg': '还款流水[%s] 没有找到可冲账合同' % (self.refund.id)}

        app.logger.info('---还款流水[%s] 冲账结束---', self.refund.id)


    # 有无减免审批中的合同
    def __check_exam_contract(self):
        commit_plan = CommitInfo.query.filter(CommitInfo.contract_id == self.contract.id,
                                              CommitInfo.type == 1,
                                              CommitInfo.result == 0
                                              ).all()
        return commit_plan





