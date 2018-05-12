#!/usr/bin/python
# -*- coding: UTF-8 -*-
import multiprocessing
import traceback
import pandas as pd
import xlrd
import os,datetime,re
from app.main.match_engine import match_by_refund, match_by_contract
from app.main.utils import countFee, countDelayDay, convert
from ..models import *
from sqlalchemy import and_
from .utils import DateStrToDate
from .. import db, app, celery


class FileExecute:
    def __init__(self,file,kind):
        from .. import config
        self.file = file
        self.file_kind = kind
        self.file_dir = config['dev'].UPLOAD_FOLD
        self.filename = None

    def execute_file(self):
        from app.tasks import batch_match_refund
        try:
            file_id = self.save_file()
            result = self.rectify(self.file_kind)
            if result['result'] != True:
                return {'issucceed':500,'message': result['message']}

            datatable = result['datatable']
            data_list = self.save_file_in_db(self.file_kind,datatable,file_id)
            if (self.file_kind == "refund"):
                batch_match_refund.apply_async(args=[file_id])
                #p = multiprocessing.Process(target=batch_match_refund, args=(file_id,))
                #app.logger.info('process start...')
                #p.start()

            return {'isSucceed':200,'message':'上传成功','file_id':file_id}
        except Exception as e:
            app.logger.error('',traceback.format_exc())
            #app.logger.error(e)
            return {'isSucceed': 500, 'message': '数据上传失败'}

    #验证模板是否正确
    def rectify(self,kind):
        result = False
        if kind == 'refund':
            result=self.rectify_refund()
        elif kind == 'plan':
            result = self.rectify_refund_plan()
        return result

    #还款流水模板验证
    def rectify_refund(self):
        try:
            datatable = pd.read_excel(self.filename)
            columns = list(datatable.columns)
            real_columns = ['支付日期', '支付时间', '客户姓名', '金额', '所在门店','渠道','收款卡号尾号','收款银行']

            if columns == real_columns:
                return {'result': True, 'datatable': datatable}
            else:
                return {"result": False, 'message': '文件表头不合法'}
        except Exception as e:
            # app.logger.error('',traceback.format_exc())
            app.logger.error(e)
            return {"result": False, 'message': e}


    #还款计划模板验证
    def rectify_refund_plan(self):
        try:
            datatable = pd.read_excel(self.filename)
            # 查看表头是否正确
            columns = list(datatable.columns)

            if (len(columns) - 9) % 2 == 0:
                tensor_max = (len(columns) - 9) // 2
                real_columns = ['合同编号', '客户姓名', '身份证号','手机号', '地区门店', '合同金额', '放款金额','放款日期', '借款期数']
                for i in range(tensor_max):
                    real_columns += ['%d期应还日期' % (i + 1), '%d期应还金额' % (i + 1)]
                if columns == real_columns:
                    return {'result': True, 'datatable': datatable}
            return {"result": False, 'message': '文件表头不合法'}
        except Exception as e:
            #app.logger.error('',traceback.format_exc())
            app.logger.error(e)
            return {"result": False, 'message': e}

    #保存文件
    def save_file(self):
        import time, copy

        file_kind = {'plan': 0, 'refund': 1}
        file_dir = os.path.join(self.file_dir)
        os.chdir(file_dir)
        t = time.strftime('%Y%m%d')
        if not os.path.exists(t):
            os.mkdir(t)

        cat = 'P' if self.file_kind == 'plan' else 'R'
        filename = '%s/%s_%u_%s' % (t, cat, int(time.time() * 1000), self.file.filename)
        self.filename = os.path.join(self.file_dir, filename)

        self.file.save(self.filename)

        upload_file = UploadFile()
        upload_file.file_name = filename
        upload_file.file_kind = file_kind[self.file_kind]
        upload_file.upload_date = datetime.datetime.now()
        upload_file.file_dir = file_dir
        db.session.add(upload_file)
        db.session.commit()

        return upload_file.id


    #将文件信息保存到数据库中
    def save_file_in_db(self,kind,datatable,file_id):
        data_list = []
        if kind == "plan":
            data_list =self.save_refund_plan(datatable,file_id)
        elif kind == "refund":
            data_list =self.save_refund(datatable,file_id)

        return data_list

    #保存合同和还款计划到数据库
    def save_refund_plan(self,datatable,file_id=None):
        contract_nos = list(datatable['合同编号'])
        try:
            for contract_no in contract_nos:
                contract_db = Contract.query.filter(Contract.contract_no==contract_no).first()
                # 检查合同号是否存在
                if contract_db: # 如果存在，该合同不予录入
                    app.logger.warn('合同号%已存在，略过',contract_no)
                    continue
                limit_table = datatable[datatable['合同编号']==contract_no]
                contract = Contract()
                contract.file_id = file_id
                contract.contract_no = str(contract_no)
                contract.customer = str(limit_table['客户姓名'].values[0])
                contract.id_number = str(limit_table['身份证号'].values[0])
                contract.mobile_no = str(limit_table['手机号'].values[0])
                contract.shop = str(limit_table['地区门店'].values[0])
                contract.contract_amount = int(limit_table['合同金额'].values[0]*100)
                contract.loan_amount = int(limit_table['放款金额'].values[0]*100)
                contract.tensor = int(limit_table['借款期数'].values[0])
                loan_date = limit_table['放款日期'].values[0]
                if loan_date==loan_date:contract.loan_date = pd.Timestamp(loan_date).to_pydatetime()
                db.session.add(contract)
                db.session.flush()

                tensor_max = (len(datatable.columns)-8)//2

                for i in range(tensor_max):
                    deadline=limit_table['%d期应还日期' % (i + 1)].values[0]
                    amount = limit_table['%d期应还金额'%(i+1)].values[0]
                    if pd.notnull(deadline) and pd.notnull(amount):#判断值是否为Nan
                        refund_plan = ContractRepay()
                        refund_plan.contract_id = contract.id
                        refund_plan.file_id = file_id
                        refund_plan.deadline = datetime.datetime.utcfromtimestamp(deadline.tolist()/1e9)
                        if not contract.repay_date:
                            contract.repay_date = refund_plan.deadline

                        refund_plan.tensor = i+1
                        refund_plan.interest = 0
                        refund_plan.principal = int(amount * 100)  # 应还本金（单位：分/人民币）
                        refund_plan.delay_day = 0  # 逾期天数
                        refund_plan.is_settled = 0  # 是否已结清（0未结清，1已结清）
                        refund_plan.amt = int(amount * 100)  # 应还金额
                        refund_plan.fee = 0  # 滞纳金
                        refund_plan.actual_amt = 0  # 应还本息
                        refund_plan.actual_fee = 0  # 应还滞纳金
                        db.session.add(refund_plan)
                    else:
                        raise Exception("数据不合法")
            db.session.commit()
            return set(contract_nos)
        except Exception as e:
            app.logger.error(e)
            db.session.rollback()
            raise

    # 保存实际还款流水
    def save_refund(self, datatable, file_id):
        from .utils import TimeString
        try:
            def getRefundTime(x):
                pay_date_str = datatable[datatable.index == x].get('支付日期').values[0]
                pay_time_str = datatable[datatable.index == x].get('支付时间').values[0]
                pay_date = pd.to_datetime(pay_date_str)
                if pay_time_str == pay_time_str: # float nan判断
                    time = TimeString(pay_time_str)  # 支持匹配正则匹配时分和时分秒
                    pay_date = pay_date.replace(hour=int(time[0]), minute=int(time[1]), second=int(time[2]))
                return pay_date

            datatable['index'] = datatable.index
            pdf = pd.DataFrame({
                'file_id': file_id,
                'refund_name': datatable['客户姓名'],
                'refund_time': datatable['index'].apply(getRefundTime),
                'method': datatable['渠道'],
                'shop': datatable['所在门店'],
                'amount': datatable['金额']*100,
                'remain_amt': datatable['金额']*100,
                'bank': datatable['收款银行'],
                'card_id': datatable['收款卡号尾号'],
            })
            pdf.to_sql("t_repayment", db.engine, if_exists='append', index=False, chunksize=1000)
            return True
        except Exception as e:
            app.logger.error(e)
            raise


class DataExecute:
    #对账处理
    def unse_get_contract(self,contract_no=None,customer=None,check_date=None,page=None,all=0):
        def convert(limit):
            if limit:return limit
            else: return "%"

        def contruct_contract_dict(contract):
            contract_dic = {}
            contract_dic['contract_no'] = contract.contract_no
            contract_dic['customer'] = contract.customer
            contract_dic['loan_amount']="%.2f"%(contract.loan_amount/100)
            contract_dic['loan_date'] = contract.loan_date.strftime('%Y-%m-%d')
            contract_dic['id_number'] = contract.id_number
            contract_dic['tensor'] = contract.tensor
            contract_dic['deal_status'] = contract.is_dealt
            contract_dic['upload_time'] = contract.create_timed.strftime("%Y-%m-%d")
            now = datetime.datetime.now()
            end_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)

            refund_plans=ContractRepay.query.filter(ContractRepay.contract_id == contract.id, ContractRepay.is_settled == 0, ContractRepay.deadline < end_time).all()
            if refund_plans:
                contract_dic['overtime_tensor']=len(refund_plans)
                contract_dic['check_status'] = 0
            else:
                contract_dic['overtime_tensor'] = 0
                contract_dic['check_status'] = 1
            return contract_dic

        if not [contract_no,customer,check_date,page]:
            return False

        if not check_date:
            start_date = datetime.datetime(1990,1,1)
            end_date = datetime.datetime.now()
        else:
            start_date = DateStrToDate(check_date,0,0,0)
            end_date = DateStrToDate(check_date,23,59,59)

        query = and_(Contract.contract_no.like(convert(contract_no)), Contract.customer.like(convert(customer)),Contract.create_time.between(start_date, end_date))
        contracts = Contract.query.filter(query).all()

        if int(all) ==0:#如果是获取未处理列表
            contracts_list = []
            now = datetime.datetime.now()
            end_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            for contract in contracts:
                overtime_plans = ContractRepay.query.filter(ContractRepay.contract_id == contract.id,
                                                         ContractRepay.is_settled == 0,
                                                         ContractRepay.deadline <= end_time).all()
                if plans:
                    contracts_list.append(contract)

        else:
            contracts_list = contracts
        num = len(contracts)

        if page:
            page=int(page)
        else:page = 1

        if (page-1)*10+10<=num:
            return_contracts = contracts_list[(page-1)*10:(page-1)*10+10]
        elif (page-1)*10<=num:
            return_contracts = contracts_list[(page-1)*10:]
        else:
            return_contracts = []

        contract_list = []
        for return_contract in return_contracts:
            contract_list.append(contruct_contract_dict(return_contract))
        result = {'isSucceed':200,'message':'','contract_list':contract_list,'num':num}
        db.session.commit()
        return result

    #合同表详情---------------------------------------------------------------------------------------------------------
    def contract_detail(self,contract_id=None):
        if contract_id:
            contract = Contract.query.filter(Contract.id == contract_id).first()
        else:
            return {'isSucceed': 505, 'message': 'contract_id不能为空'}
        if not contract:
            return {'isSucceed':500,'message':'未查询到合同'}
        contract_dic = {}
        contract_dic['contract_no'] = contract.contract_no
        contract_dic['customer'] = contract.customer
        contract_dic['mobile_no'] = contract.mobile_no
        contract_dic['id_number'] = contract.id_number
        contract_dic['tensor'] = contract.tensor
        contract_dic['contract_amount'] = "%u"%(contract.contract_amount/100)
        contract_dic['loan_amount'] = "%u"%(contract.loan_amount/100)
        contract_dic['loan_date'] = contract.loan_date.strftime("%Y-%m-%d")
        contract_dic['remain_sum']= "%u"%(contract.remain_sum/100)        #冲账余额
        plans = ContractRepay.query.filter(ContractRepay.contract_id == contract.id).all()
        #还款情况
        overtime_list = []
        overtime_sum = 0
        for plan in plans:
            overtime_amount = plan.principal+plan.interest
            overtime_sum +=overtime_amount

            delayDay = countDelayDay(plan)  # 逾期天数
            fee = countFee(contract.contract_amount, delayDay)


            plan_dict = {'deadline': plan.deadline.strftime("%Y-%m-%d"),
                         'amount': "%u" % (overtime_amount / 100),
                         'tensor': plan.tensor,
                         'settled_date': plan.settled_date.strftime(
                             "%Y-%m-%d") if plan.settled_date else None,
                         'contract_no':contract.contract_no,
                         'actual_amt': "%u" % (plan.actual_amt / 100),
                         'actual_fee': "%u" % (plan.actual_fee / 100),
                         'interest': "%u" % (plan.interest / 100),
                         'fee': "%u" % (fee / 100),
                         'actual_amt': "%u" % (plan.actual_amt / 100),
                         'actual_fee': "%u" % (plan.actual_fee / 100),
                         'is_settled': plan.is_settled,
                         'delay_day': delayDay
                         }
            overtime_list.append(plan_dict)
        contract_dic['overtime_list'] = overtime_list

        # 协商历史
        commit_history = []
        commits = CommitInfo.query.filter(CommitInfo.contract_id == contract.id).order_by(CommitInfo.create_time.desc()).all()
        for commit in commits:
            commit.remark = commit.remark if commit.remark else ''
            commit.approve_remark = commit.approve_remark if commit.approve_remark else ''
            if commit.type==1:
                remark =''
                if commit.remark:
                    remark = '减免申请：%s；'%(commit.remark)
                if  commit.approve_remark:
                    remark = remark + '审批意见：%s' % (commit.approve_remark)
            else:
                if commit.remark:
                    remark = '操作备注：'+ commit.remark
                else:
                    remark = ''
            comit_refund = {'type': commit.type, 'discount_type': commit.discount_type, 'remark': remark,
                            'apply_date': commit.apply_date.strftime("%Y-%m-%d"),
                            'apply_date': commit.apply_date.strftime("%Y-%m-%d %H:%M:%S"),
                            'applyer': commit.applyer, 'amount': "%u" % (commit.amount/100), 'remain_amt': commit.remain_amt,
                            'approve_date': commit.approve_date.strftime(
                                "%Y-%m-%d %H:%M:%S") if commit.approve_date else None,
                            'result': commit.result,
                            'create_time': commit.create_time.strftime("%Y-%m-%d %H:%M:%S")}
            commit_history.append(comit_refund)
        contract_dic['commit_history'] = commit_history

        #处理面板-最近一次的处理记录
        if commits:
            last_commit = commits[0]
            if last_commit:
                last_amount = "%u" % (last_commit.amount / 100)
                remark = '减免申请：%s；审批意见：%s' % (last_commit.remark, last_commit.approve_remark)
                commit_dic = {'type': last_commit.type, 'amount': last_amount, 'remark': remark,
                              'approve_remark': last_commit.approve_remark, 'result': last_commit.result,
                              'is_dealt': contract.is_dealt}
                contract_dic['commit'] = commit_dic
        else:
            contract_dic['commit'] = {'type': '', 'deadline': '', 'amount': '', 'remark': '', 'approve_remark': '','result': '', 'is_valid': ''}

        #实际还款
        real_pays =Repayment.query.filter(Repayment.contract_id == contract.id).order_by(Repayment.refund_time.desc()).all()
        real_pay_list=[]
        for pay in real_pays:
            real_pays = {'way': pay.method,'remain_amt':"%u" % (pay.remain_amt/100),
                         'refund_time': pay.refund_time.strftime("%Y-%m-%d %H:%M:%S"),
                         'create_time': pay.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                         'refund_name': pay.refund_name, 'amount': "%u" % (pay.amount/100)}
            real_pay_list.append(real_pays)
        contract_dic['real_pays']=real_pay_list
        return  contract_dic

    def get_unlinked_refund(self,page=None,customer=None,refund_date=None,range=None):
        if not [page,customer,refund_date,range]:
            return {'isSucceed':500,'message':'参数错误'}

        if page:page= int(page)
        else:page = 1
        if refund_date:
            start_date = DateStrToDate(refund_date,0,0,0)
            end_date = DateStrToDate(refund_date,23,23,23)
        else:
            start_date = datetime.datetime(1990, 1, 1)
            end_date = datetime.datetime.now()
        if range:
            min_sum,max_sum = re.findall("(.+)-(.+)",range)[0]
            min_sum,max_sum = int(min_sum),int(max_sum)
        else:
            min_sum,max_sum = 0,10**9
        if not customer:
            customer = "%"

        unlinked_refunds = Repayment.query.filter(Repayment.remain_amt >0,
                                                  Repayment.create_time.between(start_date, end_date),
                                                  Repayment.amount.between(min_sum, max_sum),
                                                  Repayment.refund_name.like(customer)).paginate(int(page), per_page=10, error_out=False)
        page_refunds = unlinked_refunds.items
        num = unlinked_refunds.total
        unlinked_list = []
        for unlinked_refund in page_refunds:
            unlinked_dic = {'refund_date': unlinked_refund.refund_time.strftime("%Y-%m-%d"),
                            'refund_time': unlinked_refund.refund_time.strftime('%H:%M:%S'),
                            'refund_name': unlinked_refund.refund_name, 'card_id': unlinked_refund.card_id,
                            'amount': "%u" % (unlinked_refund.amount / 100),
                            'remain_amt': "%u" % (unlinked_refund.remain_amt / 100),
                            'type': unlinked_refund.method, 'refund_id': unlinked_refund.id}
            unlinked_list.append(unlinked_dic)
        return {'isSucceed':200,'num':num,'unlinked_list':unlinked_list}


    #修改还款信息
    def create_commit(self,contract_no,user_id,amount,commit,type=0,discount_type=0):
        contract = Contract.query.filter(Contract.contract_no==contract_no).first()
        if not contract:
            return {'isSucceed': 500, 'message': '未找到合同'}
        now = datetime.datetime.now()

        commit_refund = CommitInfo()
        commit_refund.contract_id = contract.id
        commit_refund.apply_date = now  # 申请日期
        commit_refund.type = int(type)  # 协商类型
        commit_refund.remark = commit  # 备注
        commit_refund.applyer = int(user_id)
        commit_refund.is_valid = 0  # 0、有效；-1；无效
        if type == '1':  # 申请减免
            commit_refund.result = 0  # 0、待审核；100、通过；200、拒绝
            commit_refund.discount_type = int(discount_type)  # 减免类型
            commit_refund.amount = int(amount) * 100  # 协商金额
            commit_refund.remain_amt = int(amount) * 100  # 协商金额
        if type == '2':  # 移交外催
            commit_refund.result = 100  # 0、待审核；100、通过；200、拒绝
            contract.is_settled = 200  # 合同状态==》移交外催
        if type == '0':  # 提醒还款
            commit_refund.result = 100  # 0、待审核；100、通过；200、拒绝

        db.session.add(commit_refund)  # 保存协商还款信息

        contract.is_dealt = 1  # 合同当天任务状态==》已处理
        db.session.add(contract)  # 修改合同状态
        db.session.commit()

        return {'isSucceed':200,'message':'创建完成'}

    # 获取协商还款列表--对账审核
    def get_commits(self, customer=None, applyer=None, shop=None, page=1):

        query = CommitInfo.query.outerjoin(Contract).filter(CommitInfo.is_valid == 0,
                                                            CommitInfo.result == 0,
                                                            CommitInfo.type == 1)
        if customer:
            query = query.filter(Contract.customer.like(customer))
        if applyer:
            query = query.filter(CommitInfo.applyer.like(applyer))
        if shop:
            query = query.filter(Contract.shop.like(shop))

        commits = query.order_by(CommitInfo.create_time.desc()).paginate(int(page), per_page=10, error_out=False)

        page_commits = commits.items
        num = commits.total

        commit_list = []
        # commits = self.get_by_page(lists=commits,page=page)
        now = datetime.datetime.now()
        deadline = datetime.datetime(now.year, now.month, now.day, 0, 0, 0)
        for commit in page_commits:
            contract = commit.contract
            refunds = commit.plans
            commit_dic = {
                'contract_no':contract.contract_no,
                'customer':contract.customer,
                'shop': contract.shop,
                'overtime_num':len(refunds),
                'commit_id':commit.id,
                'result':commit.result,
                'commit_amount':"%u"%(commit.amount/100),
                'remark':commit.remark[:5]+'...' if commit.remark else '',
                'applyer':commit.applyer
            }
            commit_list.append(commit_dic)
        return {'isSucceed':200,'commit_list':commit_list,'num':num}

    #获取协商还款详情
    def get_commit_detail(self,commit_id):
        commit = CommitInfo.query.filter(CommitInfo.id == commit_id, CommitInfo.is_valid == 0).first()
        if not commit:
            return {'isSucceed': 500, 'message': '未找到该协商计划'}
        now = datetime.datetime.now()
        deadline = datetime.datetime(now.year, now.month, now.day, 0, 0, 0)
        contract = commit.contract
        plans = commit.plans
        overtime_list = []
        overtime_sum = 0
        for overtime_plan in plans:
            overtime_amount = overtime_plan.principal + overtime_plan.interest
            overtime_sum += overtime_amount
            plan_dict = {'amount': "%u"%(overtime_amount/100),
                         'tensor': overtime_plan.tensor,
                         'settled_date': overtime_plan.settled_date.strftime(
                             "%Y-%m-%d") if overtime_plan.refund_name else None,
                         }
            overtime_list.append(plan_dict)
        commit_dict = {'isSucceed': 200, 'contract_no': contract.contract_no, 'customer': contract.customer,
                       'loan_amount': "%u" % (contract.loan_amount / 100),
                       'tensor': contract.tensor, 'ovetime_list': overtime_list, 'overtime_num': len(overtime_list),
                       'overtime_sum': "%u" % (overtime_sum / 100),
                       'remain_sum': "%u" % (contract.remain_sum / 100), 'result': commit.result,
                       'commit_id': commit_id, 'commit_amount': '%u' % (commit.amount / 100), 'remark': commit.remark}
        return commit_dict


    #协商还款审批
    def approve_commit(self,commit_id,result,user_id,approve_remark=None):
        commit = CommitInfo.query.filter(CommitInfo.id == int(commit_id), CommitInfo.is_valid == 0,
                                         CommitInfo.result == 0, CommitInfo.type == 1).first()
        if not commit:
            return {'isSucceed':500,'message':'未找到该协商计划'}
        commit.result = int(result)
        commit.approver= user_id
        commit.approve_remark = approve_remark
        commit.approve_date = datetime.datetime.now()
        contract = commit.contract

        # 减免审批通过后执行冲账
        if commit.type == 1 :
            if commit.result == 100:
                result = match_by_contract(contract)
                app.logger.info(result)
            elif commit.result == 200:
                contract.is_dealt = 0 #调整为未处理状态

        db.session.add(contract)
        db.session.commit()
        return {'isSucceed':200,'message':'审批成功'}

    #将还款记录与合同对应冲账
    def link_refund_to_contract(self,contract_no,contract_id,refund_id):
        contract = None
        if contract_no:
            contract = Contract.query.filter(Contract.contract_no == contract_no).first()

        if contract_id:
            contract = Contract.query.filter(Contract.id == contract_id).first()
        refund = Repayment.query.filter(Repayment.id==int(refund_id)).first()
        if  not refund:
            return {'isSucceed': 500, 'message': '未找到有效流水'}

        result = match_by_contract(contract, refund)
        if result:
            return {'isSucceed': 500, 'message': result.msg}
        else:
            return {'isSucceed': 200, 'message': '冲账成功！'}

    #还款流水重新匹配
    def refund_re_match(self,refund_id):
        refund = Repayment.query.filter(Repayment.id==refund_id,Repayment.contract_id.is_(None)).first()
        if not refund:
            return {'isSucceed': 500, 'message': '未找到还款流水'}
        from .match_engine import match_by_refund
        result = match_by_refund(refund)
        if result:
            return {'isSucceed': 500, 'message': result.msg}
        else:
            return {'isSucceed': 200, 'message': '重新匹配成功！'}


    def update_contract(self,contract_no):
        contract = Contract.query.filter(Contract.contract_no == contract_no).first()
        commit_plan = CommitInfo.query.filter(CommitInfo.contract_id == contract.id, CommitInfo.is_valid == 1,
                                              CommitInfo.is_settled == 0).first()
        fund_plans = True

        if commit_plan:  # 首先计算协商还款数
            deserve_refund_sum = commit_plan.amount
            if contract.remain_sum >= deserve_refund_sum:  # 如果余额比需还款的金额大,则更新
                if commit_plan.type == 2 or commit_plan.type ==1:
                    contract.is_settled = 1
                    contract.is_dealt = 1
                    db.session.add(contract)
                    fund_plans = False
                commit_plan.is_settled = 1
                plans = commit_plan.plans
                for plan in plans:  # 将协商还款所对应的还款期数全部冲正
                    plan.is_settled = 1
                    plan.settled_date = datetime.datetime.now()
                    db.session.add(plan)
                db.session.add(commit_plan)
            else:  # 如果不足，则需要处理
                fund_plans = False
        db.session.commit()

        if fund_plans:  # 如果有未还清的协商计划，或合同被协商还款计划结清，则fund_plan==False,不对正常还款计划进行更新
            plans = ContractRepay.query.filter(ContractRepay.contract_id == contract.id,
                                                     ContractRepay.is_settled == 0,
                                                     ContractRepay.deadline < datetime.datetime.now()).all()
            if not plans:  # 第二步检查是否还有逾期未处理
                now = datetime.datetime.now()
                end_time = datetime.datetime(now.year, now.month, now.day + 1, 0, 0, 0)
                refund_plan = ContractRepay.query.filter(ContractRepay.contract_id == contract.id,
                                                      ContractRepay.is_settled == 0,
                                                      ContractRepay.deadline == end_time).first()
                if refund_plan:  # 检查是否有正常还款中的期数
                    deserve_refund_sum = 0  # 计算总需要还款数

                    deserve_refund_sum += refund_plan.principal
                    deserve_refund_sum += refund_plan.interest
                    if contract.remain_sum >= deserve_refund_sum:  # 如果余额比需还款的金额大,则更新
                        refund_plan.is_settled = 1
                        refund_plan.settled_date = datetime.datetime.now()
                        db.session.add(refund_plan)
                        contract.is_dealt = 1  # 无协商还款和正常还款计划未处理
                        contract.remain_sum -= deserve_refund_sum
                        db.session.add(contract)
                    else:  # 如果不足，则需要处理
                        contract.is_dealt = 0
                        db.session.add(contract)
            else:  # 如果有逾期的话，也需要处理
                contract.is_dealt = 0
                db.session.add(contract)

        db.session.commit()

    #页数
    def get_by_page(self,lists,page):
        page = int(page)
        num = len(lists)
        if (page - 1) * 10 + 10 <= num:
            lists = lists[(page - 1) * 10:(page - 1) * 10 + 10]
        elif (page - 1) * 10 <= num:
            lists = lists[(page - 1) * 10:]
        else:
            lists = []
        return lists

    def test(self):
        from .sqlhelper import  delete_contract_by_no
        delete_contract_by_no(['200803281000','1111'])

    def get_newest_date(self):
        from .sqlhelper import refund_newest_date
        refunds = refund_newest_date()
        refund_list = []
        if refunds:
            for refund in refunds:
                refundsStr = {'shop':refund['shop'],'way':refund['way'],'refundTime':refund['refund_time'].strftime("%Y-%m-%d %H:%M:%S")}
                refund_list.append(refundsStr)
            result_dic = {'isSucceed':200,'refund_list':refund_list,'message':'查询各门店最新支付时间成功！'}
        else:
            result_dic = {'isSucceed': 500, 'refund_list': '', 'message': '查询各门店最新支付时间失败！'}
        return result_dic
    #还款流水查询
    def search_refund(self,file_id=None,is_match=None,refund_name=None,refund_time=None,shop=None,page='1'):
        def get_query():
            query = Repayment.query
            if file_id:
                query = query.filter(Repayment.file_id == file_id)
            if refund_name:
                query = query.filter(Repayment.refund_name == refund_name)
            if is_match:
                query = query.filter(Repayment.t_status == is_match)
            if shop:  # 门店
                query = query.filter(Repayment.shop.like(shop))
            if refund_time:
                start_date = DateStrToDate(refund_time, 0, 0, 0)
                end_date = DateStrToDate(refund_time, 23, 59, 59)
                query = query.filter(Repayment.refund_time.between(start_date, end_date))
            else:
                start_date = datetime.datetime(1990, 1, 1)
                end_date = datetime.datetime.now()
                query = query.filter(Repayment.refund_time.between(start_date, end_date))
            return query.order_by(Repayment.create_time.desc(),Repayment.refund_time.desc())

        pagination = get_query().paginate(int(page), per_page=10, error_out=False)
        page_refunds = pagination.items
        num = pagination.total

        search_refund_list = []
        if page_refunds:
            for refund in page_refunds:
                refundsStr = {'way': refund.method, 'refundTime': refund.refund_time.strftime("%Y-%m-%d %H:%M:%S"),
                              'create_time': refund.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                              'refund_name': refund.refund_name, 'file_id': refund.file_id,'shop': refund.shop,
                              'remain_amt': "%u" % (refund.remain_amt / 100),
                              'contract_id': refund.contract_id, 'card_id': refund.card_id,
                              'refund_id': refund.id, 't_status': refund.t_status,
                              'amount': "%u" % (refund.amount / 100)}
                search_refund_list.append(refundsStr)
            result_dic = {'isSucceed': 200, 'search_refund_list': search_refund_list, 'message': '查询还款流水成功！','num':num}
        else:
            result_dic = {'isSucceed': 200, 'search_refund_list': search_refund_list, 'message': '查询还款流水成功！','num':num}
        return  result_dic

    def retry_refund(self,refund_id):
        refund = Repayment.query.filter(Repayment.id == refund_id).first()
        return match_by_refund(refund)

    # 对账处理/贷款列表
    def get_deal_refund(self,query_form):

        def contruct_contract_dict(contract):
            contract_dic = {}
            contract_dic['shop'] = contract.shop
            contract_dic['contract_no'] = contract.contract_no
            contract_dic['contract_id'] = contract.id
            contract_dic['customer'] = contract.customer
            contract_dic['loan_amount'] = "%u" % (contract.loan_amount / 100)
            contract_dic['contract_amount'] = "%u" % (contract.contract_amount / 100)
            contract_dic['loan_date'] = contract.loan_date.strftime('%Y-%m-%d')
            delay_days = None
            if contract.repay_date:
                delay_days = (datetime.datetime.now().date() - contract.repay_date).days
            contract_dic['delay_days'] = delay_days
            contract_dic['id_number'] = contract.id_number
            contract_dic['tensor'] = contract.tensor
            contract_dic['is_settled'] = contract.is_settled
            contract_dic['deal_status'] = contract.is_dealt
            contract_dic['file_id'] = contract.file_id
            contract_dic['upload_time'] = contract.created_time.strftime("%Y-%m-%d")
            contract_dic['loan_date'] = contract.loan_date.strftime("%Y-%m-%d")
            return contract_dic

        def get_query():
            now = datetime.datetime.now().replace(hour=0,minute=1,second=0, microsecond=0)

            query = Contract.query
            if query_form.contract_no:  # 合同编号
                query = query.filter(Contract.contract_no.like(convert(query_form.contract_no)))
            if query_form.customer:  # 客户名字
                query = query.filter(Contract.customer.like(convert(query_form.customer)))
            if query_form.shop:  # 门店
                query = query.filter(Contract.shop.like(convert(query_form.shop)))
            if query_form.is_dealt:  # 1为已处理，0为未处理
                query = query.filter(Contract.is_dealt == query_form.is_dealt)
            if query_form.is_settled:  # 0、还款中；100、逾期；200、移交外催；300、结清)
                query = query.filter(Contract.is_settled == query_form.is_settled)
            if query_form.id_number:  # 证件号码
                query = query.filter(Contract.id_number == query_form.id_number)
            if query_form.file_id:  # 合同文件编号
                query = query.filter(Contract.file_id == query_form.file_id)
            if query_form.from_yu_day:
                f_date = now - datetime.timedelta(days=int(query_form.from_yu_day))
                ff_date = f_date.replace(hour=23,minute=59,second=59, microsecond=999999)
                query = query.filter(Contract.repay_date <= ff_date)
            if query_form.to_yu_day:
                t_date = now - datetime.timedelta(days=int(query_form.to_yu_day))
                tt_date = t_date.replace(hour=0,minute=0,second=0, microsecond=0)
                query = query.filter(Contract.repay_date >= tt_date)


            if query_form.repay_date and query_form.repay_date!='null':
                query = query.filter(Contract.repay_date <= query_form.repay_date)
            return query.order_by(Contract.loan_date.desc(),Contract.contract_no.desc())

        contracts = get_query().paginate(int(query_form.page), per_page=10, error_out=False)
        page_contracts = contracts.items
        num = contracts.total
        contract_list = []
        for contract in page_contracts:
            contract_list.append(contruct_contract_dict(contract))
        result = {'isSucceed': 200, 'message': '', 'contract_list': contract_list, 'num': num}
        return result

