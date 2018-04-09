#!/usr/bin/python
# -*- coding: UTF-8 -*-
import pandas as pd
import xlrd
import os,datetime,re
from ..models import Contract,UploadFile,tRefundPlan,Refund,CommitRefund
from sqlalchemy import and_
from .back_server import DateStrToDate
from .. import db

class FileExecute:
    def __init__(self,file,kind):
        from .. import config
        self.file = file
        self.file_kind = kind
        self.file_dir = config['dev'].UPLOAD_FOLD

    def execute_file(self):
        try:
            result = self.rectify(self.file_kind)
            if result['result'] != True:
                return {'issucceed':500,'message': result['message']}

            file_id = self.save_file()
            datatable = result['datatable']
            contract_list = self.save_file_in_db(self.file_kind,datatable,file_id)
            for contract in contract_list:
                self.update_contract(contract)
            return {'isSucceed':200,'message':'上传成功','file_id':file_id}
        except:
            return {'isSucceed': 500, 'message': '模板有误'}


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
        result = False
        try:
            datatable = pd.read_excel(self.file, sheet_name='对账流水表')
            columns = list(datatable.columns)
            real_columns = ['支付日期', '支付时间', '客户姓名', '金额', '所在门店','渠道','收款卡号尾号','收款银行']

            if columns == real_columns:
                result = True
                return {'result': result, 'datatable': datatable}
            else:
                return {"result": result, 'message': '列缺失'}
        except:
            return {"result": result, 'message': '模板格式不正确'}


    #还款计划模板验证
    def rectify_refund_plan(self):
        result = False
        try:
            datatable = pd.read_excel(self.file, sheet_name='Sheet1')
            # 查看表头是否正确
            columns = list(datatable.columns)
            if (len(columns) - 8) % 2 == 0:
                tensor_max = (len(columns) - 8) // 2
                real_columns = ['合同编号', '客户姓名', '身份证号', '地区门店', '合同金额', '放款金额','放款日期', '借款期数']
                for i in range(tensor_max):
                    real_columns += ['%d期应还日期' % (i + 1), '%d期应还金额' % (i + 1)]
                if columns == real_columns:
                    result = True
                    return {'result': result, 'datatable': datatable}
            return {"result": result, 'message': '模板格式不正确'}
        except:
            return {"result": result, 'message': '模板格式不正确'}

    #保存文件
    def save_file(self):
        import time
        file_kind = {'plan':0,'refund':1}
        filename  = self.file.filename[:-4]+str(int(time.time()*1000))+'.xls'
        file_dir = os.path.join(self.file_dir,filename)
        self.file.save(file_dir)

        upload_file = UploadFile()
        upload_file.file_name = filename
        upload_file.file_kind = file_kind[self.file_kind]
        upload_file.upload_date = datetime.datetime.now()
        upload_file.file_dir = file_dir
        db.session.add(upload_file)
        db.session.commit()

        file = UploadFile.query.filter(UploadFile.file_name==filename).first()
        return file.id


    #将文件信息保存到数据库中
    def save_file_in_db(self,kind,datatable,file_id):
        if kind == "plan":
            contract_list =self.save_refund_plan(datatable,file_id)
        elif kind == "refund":
            contract_list =self.save_refund(datatable,file_id)
        else:
            contract_list = False
        return contract_list

    #保存还款计划函数
    def save_refund_plan(self,datatable,file_id=None):
        from .sqlhelper import delete_contract_by_no
        contract_nos = list(datatable['合同编号'])
        try:
            for contract_no in contract_nos:
                contract_db = Contract.query.filter(Contract.contract_no==contract_no).first()#检查合同号是否存在
                if contract_db:continue#如果存在，该合同不予录入
                limit_table = datatable[datatable['合同编号']==contract_no]
                contract = Contract()
                contract.file_id = file_id
                contract.contract_no = str(contract_no)
                contract.customer = str(limit_table['客户姓名'].values[0])
                contract.id_number = str(limit_table['身份证号'].values[0])
                contract.shop = str(limit_table['地区门店'].values[0])
                contract.contract_amount = int(limit_table['合同金额'].values[0]*100)
                contract.loan_amount = int(limit_table['放款金额'].values[0]*100)
                contract.tensor = int(limit_table['借款期数'].values[0])
                loan_date = limit_table['放款日期'].values[0]
                if loan_date==loan_date:contract.loan_date = pd.Timestamp(loan_date).to_pydatetime()
                db.session.add(contract)
                db.session.commit()

                contract = Contract.query.filter(Contract.contract_no==contract_no).first()
                tensor_max = (len(datatable.columns)-8)//2
                refund_ok_flag = True
                for i in range(tensor_max):
                    deadline=limit_table['%d期应还日期' % (i + 1)].values[0]
                    amount = limit_table['%d期应还金额'%(i+1)].values[0]
                    if (pd.isnull(deadline) and pd.notnull(amount)) or (pd.isnull(amount) and pd.notnull(deadline)):
                        refund_ok_flag = False
                        break
                    elif pd.notnull(deadline) and pd.notnull(amount):#判断值是否为Nan
                        refund_plan = tRefundPlan()
                        refund_plan.contract_id = contract.id
                        refund_plan.file_id = file_id
                        refund_plan.deadline = pd.Timestamp(deadline).to_pydatetime()+datetime.timedelta(days=1)
                        refund_plan.tensor = i+1
                        refund_plan.principal = int(amount*100)
                        refund_plan.interest = 0
                        db.session.add(refund_plan)
                    else:break

                if refund_ok_flag:
                    db.session.commit()
                else:
                    delete_contract_by_no(contract_nos)
                    return False

            return set(contract_nos)
        except:
            delete_contract_by_no(contract_nos)
            return False


    def save_refund(self,datatable,file_id=None):
        from .back_server import TimeString
        try:
            contract_list = []
            for index in datatable.index:
                note = datatable.loc[index].values
                date = pd.Timestamp(note[0]).to_pydatetime()
                time = TimeString(note[1])#支持匹配正则匹配时分和时分秒
                if not time : time = (12,0,0)
                new_date = date.replace(hour=int(time[0]), minute=int(time[1]), second=int(time[2]))
                customer,amount,shop,refund_type,card_id,bank = note[2],note[3],note[4],note[5],note[6],note[7]
                contracts = Contract.query.filter(Contract.customer==customer,Contract.is_settled ==0).all()

                refund = Refund()
                refund.file_id = file_id
                refund.refund_time = new_date
                refund.refund_name = customer
                refund.method = refund_type
                refund.amount = int(amount*100)

                if len(contracts)==1:
                    contract = contracts[0]
                    contract_list.append(contract.contract_no)
                    start_time = (new_date + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)
                    refund_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,tRefundPlan.is_settled==0,tRefundPlan.settled_by_commit.is_(None),tRefundPlan.deadline<=start_time).all()
                    if len(refund_plans)==1:#如果仅仅有一期逾期且逾期应还时间为还款当天，则冲平
                        refund_plan = refund_plans[0]
                        plan_amount = refund_plan.principal + refund_plan.interest
                        if refund_plan.deadline == start_time and refund.amount>=plan_amount:
                            refund.amount-=plan_amount
                    refund.contract_id = contract.id
                    contract.refund_sum+= refund.amount
                    contract.remain_sum+=refund.amount
                    db.session.add(contract)

                if bank!=bank:
                    refund.bank = None
                    refund.card_id = None
                else:
                    refund.bank = bank
                    refund.card_id = int(card_id)

                db.session.add(refund)
            db.session.commit()
            return set(contract_list)
        except:
            return False

    def update_contract(self,contract_no):
        contract = Contract.query.filter(Contract.contract_no==contract_no).first()
        commit_plan  = CommitRefund.query.filter(CommitRefund.contract_id==contract.id,CommitRefund.is_valid==1,CommitRefund.is_settled==0).first()
        fund_plans = True

        if commit_plan:#首先计算协商还款数
            deserve_refund_sum = commit_plan.amount
            if contract.remain_sum>=deserve_refund_sum:#如果余额比需还款的金额大,则更新
                if commit_plan.type == 2 or commit_plan.type ==1:
                    contract.is_settled = 1
                    contract.is_dealt  =1
                    db.session.add(contract)
                    fund_plans = False
                commit_plan.is_settled = 1
                plans = commit_plan.plans
                for plan in plans:#将协商还款所对应的还款期数全部冲正
                    plan.is_settled = 1
                    plan.settled_date=  datetime.datetime.now()
                    db.session.add(plan)
                db.session.add(commit_plan)
            else:#如果不足，则需要处理
                fund_plans = False
        db.session.commit()

        if fund_plans:#如果有未还清的协商计划，或合同被协商还款计划结清，则fund_plan==False,不对正常还款计划进行更新
            overtime_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,tRefundPlan.is_settled == 0,tRefundPlan.deadline<datetime.datetime.now()).all()
            if not overtime_plans:#第二步检查是否还有逾期未处理
                now = datetime.datetime.now()
                end_time = datetime.datetime(now.year, now.month, now.day+1, 0,0,0)
                refund_plan = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,tRefundPlan.is_settled == 0,tRefundPlan.deadline==end_time).first()
                if refund_plan:#检查是否有正常还款中的期数
                    deserve_refund_sum = 0#计算总需要还款数

                    deserve_refund_sum+=refund_plan.principal
                    deserve_refund_sum+=refund_plan.interest
                    if contract.remain_sum>=deserve_refund_sum:#如果余额比需还款的金额大,则更新
                        refund_plan.is_settled = 1
                        refund_plan.settled_date = datetime.datetime.now()
                        db.session.add(refund_plan)
                        contract.is_dealt = 1  # 无协商还款和正常还款计划未处理
                        contract.remain_sum-=deserve_refund_sum
                        db.session.add(contract)
                    else:#如果不足，则需要处理
                        contract.is_dealt = 0
                        db.session.add(contract)
            else:#如果有逾期的话，也需要处理
                contract.is_dealt = 0
                db.session.add(contract)

        db.session.commit()




class DataExecute:
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
            contract_dic['upload_time'] = contract.create_time.strftime("%Y-%m-%d")
            now = datetime.datetime.now()
            end_time = now.replace(hour=0, minute=0, second=0) + datetime.timedelta(days=1)

            refund_plans=tRefundPlan.query.filter(tRefundPlan.contract_id==contract.id,tRefundPlan.is_settled==0,tRefundPlan.deadline<end_time).all()
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
            end_time = now.replace(hour=0, minute=0, second=0) + datetime.timedelta(days=1)
            for contract in contracts:
                overtime_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,
                                                          tRefundPlan.is_settled == 0,
                                                          tRefundPlan.deadline <= end_time ).all()
                if overtime_plans:
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

    #合同表详情
    def contract_detail(self,contract_no,is_overtime=1):
        if not contract_no:
            return {'isSucceed':500,'message':'未接收合同号'}
        contract = Contract.query.filter(Contract.contract_no==contract_no).first()
        if not contract:
            return {'isSucceed':500,'message':'未查询到合同'}
        contract_dic = {}
        contract_dic['contract_no'] = contract.contract_no
        contract_dic['customer'] = contract.customer
        contract_dic['id_number'] = contract.id_number
        contract_dic['tensor'] = contract.tensor
        contract_dic['remain_sum']= "%.2f"%(contract.remain_sum/100)
        now = datetime.datetime.now()
        end_time = now.replace(hour=0,minute=0,second=0)+datetime.timedelta(days=1)
        if int(is_overtime)==1:
            overtime_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id, tRefundPlan.is_settled == 0,tRefundPlan.deadline<=end_time).all()
        else:
            overtime_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id).all()
        overtime_list = []
        overtime_sum = 0
        if overtime_plans:
            for overtime_plan in overtime_plans:
                overtime_amount = overtime_plan.principal+overtime_plan.interest
                overtime_sum +=overtime_amount
                plan_dict = {'deadline':(overtime_plan.deadline-datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                             'amount':"%.2f"%(overtime_amount/100),
                             'tensor':overtime_plan.tensor,
                             'settled_date':overtime_plan.settled_date.strftime("%Y-%m-%d") if overtime_plan.settled_date else None,
                             'overtime_date':(now-overtime_plan.deadline).days+1
                             }
                settled_status = {'逾期':[0,0],'还款中':[1,0],'正常结清':[0,1],'提前结清':[1,1]}
                refund_status = [0 if overtime_plan.deadline<datetime.datetime.now() else 1,1 if overtime_plan.is_settled ==1 else 0]
                for status in settled_status:
                    if settled_status[status] == refund_status:
                        plan_dict['refund_status'] = status

                overtime_list.append(plan_dict)
            contract_dic['check_status'] = 0
        else:
            contract_dic['check_status'] = 1

        unsettled_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,tRefundPlan.is_settled == 0).all()
        unsettled_amount = 0
        for unsettled_plan in unsettled_plans:
            amount = unsettled_plan.principal+unsettled_plan.interest
            unsettled_amount+=amount
        contract_dic['unsettled_amount'] = "%.2f"%(unsettled_amount/100)#提前结清的金额
        contract_dic['dealt_status'] =contract.is_dealt
        contract_dic['overtime_list'] = overtime_list
        contract_dic['overtime_num'] = len(overtime_list)
        contract_dic['overtime_sum'] = '%.2f'%(overtime_sum/100)
        commit = CommitRefund.query.filter(CommitRefund.contract_id==contract.id).order_by(CommitRefund.create_time.desc()).first()
        if commit:
            commit_dic = {'type': commit.type, 'deadline': commit.deadline.strftime('%Y-%m-%d'),
                          'amount': "%.2F" % (commit.amount / 100),
                          'remark': commit.remark, 'approve_remark': commit.approve_remark,'result':commit.result,'is_valid':commit.is_valid}
            contract_dic['commit']=commit_dic
        else:
            contract_dic['commit']={'type':'','deadline':'','amount':'','remark':'','approve_remark':'','result':'','is_valid':''}
        #实际还款
        from .sqlhelper import get_real_pays
        real_pays =get_real_pays(contract.id)
        real_pay_list=[]
        for pay in real_pays:
            real_pays = {'amount': pay['amount'], 'way': pay['way'],
                         'refund_time': pay['refund_time'].strftime("%Y-%m-%d %H:%M:%S"),
                         'refund_name': pay['refund_name'], 'amount': pay['amount']}
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

        unlinked_refunds = Refund.query.filter(Refund.contract_id.is_(None),Refund.create_time.between(start_date,end_date),Refund.amount.between(min_sum,max_sum),
                                               Refund.refund_name.like(customer)).all()
        if unlinked_refunds:
            num = len(unlinked_refunds)
            unlinked_refunds=self.get_by_page(lists=unlinked_refunds,page=page)
            unlinked_list = []
            for unlinked_refund in unlinked_refunds:
                unlinked_dic = {'refund_date':unlinked_refund.refund_time.strftime("%Y-%m-%d"),'refund_time':unlinked_refund.refund_time.strftime('%H:%M:%S'),
                                'refund_name':unlinked_refund.refund_name,'card_id':unlinked_refund.card_id,'amount':"%.2f"%(unlinked_refund.amount/100),
                                'type':unlinked_refund.method,'refund_id':unlinked_refund.id}
                unlinked_list.append(unlinked_dic)
            return {'isSucceed':200,'num':num,'unlinked_list':unlinked_list}
        return {'isSucceed':200,'unlinked_list':[]}



    def create_commit(self,contract_no,user_id,deadline,amount,commit,type=0):
        contract = Contract.query.filter(Contract.contract_no==contract_no).first()
        if not contract:
            return {'isSucceed': 500, 'message': '未找到合同'}
        now = datetime.datetime.now()

        commit_refund = CommitRefund()
        commit_refund.is_valid = 2#0失效，1有效，2未审核
        commit_refund.contract_id = contract.id
        commit_refund.apply_date = now
        commit_refund.type = int(type)
        commit_refund.is_settled = 0
        if type!=2:
            commit_refund.applyer = int(user_id)
            commit_refund.deadline = DateStrToDate(deadline,23,59,59)
            commit_refund.amount = int(amount)*100
            commit_refund.remark = commit
        contract.is_dealt =1
        db.session.add(commit_refund)
        db.session.add(contract)
        db.session.commit()

        commit_refund = CommitRefund.query.filter(CommitRefund.contract_id == contract.id,CommitRefund.deadline == DateStrToDate(deadline,23,59,59)).first()
        refund_plans = contract.refund_plans
        now = datetime.datetime.now()
        end_time = now.replace(hour=0,minute=0,second=0)+datetime.timedelta(days=1)
        for refund_plan in refund_plans:
            if refund_plan.is_settled == 0 and refund_plan.deadline<=end_time:
                refund_plan.settled_by_commit = commit_refund.id
                db.session.add(refund_plan)
        db.session.commit()
        return {'isSucceed':200,'message':'创建完成'}

    #获取协商还款列表
    def get_commits(self,customer=None,applyer=None,page=1):
        if not[customer,applyer,page]:
            return {'isSucceed':500,',message':'参数错误'}
        research_dict = {'customer':customer,'applyer':applyer}
        for limit in research_dict:
            if research_dict[limit]!='':pass
            else:research_dict[limit]='%'

        commits = CommitRefund.query.outerjoin(Contract).filter(Contract.customer.like(research_dict['customer']),CommitRefund.applyer.like(research_dict['applyer']),
                                                                CommitRefund.is_valid==2).all()
        num = len(commits)
        commit_list = []
        commits = self.get_by_page(lists=commits,page=page)

        for commit in commits:
            if commit.deadline<datetime.datetime.now():
                commit.is_valid =0#如果过期的commit制定为0
                db.session.add(commit)
                continue
            contract = commit.contract
            refunds = commit.plans
            commit_dic = {
                'contract_no':contract.contract_no,
                'customer':contract.customer,
                'overtime_num':len(refunds),
                'commit_id':commit.id,
                'result':commit.result,
                'commit_amount':"%.2f"%(commit.amount/100),
                'remark':commit.remark[:5]+'...' if commit.remark else ' ',
                'deadline':commit.deadline.strftime("%Y-%m-%d"),
                'applyer':commit.applyer
            }
            commit_list.append(commit_dic)
        db.session.commit()
        return {'isSucceed':200,'commit_list':commit_list,'num':num}

    #获取协商还款详情
    def get_commit_detail(self,commit_id):
        commit = CommitRefund.query.filter(CommitRefund.id==commit_id,CommitRefund.is_valid!=0).first()
        if not commit:
            return {'isSucceed': 500, 'message': '未找到该协商计划'}
        if commit.deadline<=datetime.datetime.now():#如果过期更新
            commit.is_valid = 0
            db.session.add(commit)
            db.session.commit()
            return {'isSucceed': 500, 'message': '未找到该协商计划'}
        contract = commit.contract
        overtime_plans = commit.plans
        overtime_list = []
        overtime_sum = 0
        for overtime_plan in overtime_plans:
            overtime_amount = overtime_plan.principal + overtime_plan.interest
            overtime_sum += overtime_amount
            plan_dict = {'deadline': overtime_plan.deadline.strftime("%Y-%m-%d"),
                         'amount': "%.2f"%(overtime_amount/100),
                         'tensor': overtime_plan.tensor,
                         'settled_date': overtime_plan.settled_date.strftime(
                             "%Y-%m-%d") if overtime_plan.settled_date else None,
                         }
            overtime_list.append(plan_dict)
        commit_dict = {'isSucceed':200,'contract_no':contract.contract_no,'customer':contract.customer,'loan_amount':"%.2f"%(contract.loan_amount/100),'tensor':contract.tensor,
                       'ovetime_list':overtime_list,'overtime_num':len(overtime_list),'overtime_sum':"%.2f"%(overtime_sum/100),'remain_sum':"%.2f"%(contract.remain_sum/100),'result':commit.result,'commit_id':commit_id,'commit_amount':'%.2f'%(commit.amount/100),'remark':commit.remark,'deadline':commit.deadline.strftime('%Y-%m-%d')}
        return commit_dict


    #协商还款审批
    def approve_commit(self,commit_id,result,user_id,approve_remark=None):
        commit=CommitRefund.query.filter(CommitRefund.id==int(commit_id),CommitRefund.is_valid==2,CommitRefund.is_settled==0).first()
        if not commit:
            return {'isSucceed':500,'message':'未找到该协商计划'}
        if int(result)==1:
            commit.is_valid = 1
        else:commit.is_valid = 0
        commit.result = int(result)
        commit.approver= user_id
        commit.approve_remark = approve_remark
        commit.approve_date = datetime.datetime.now()
        db.session.add(commit)
        db.session.commit()
        contract = commit.contract
        self.update_contract(contract.contract_no)#更新
        return {'isSucceed':200,'message':'审批成功'}

    #将还款记录与合同对应冲账
    def link_refund_to_contract(self,contract_no,refund_id):
        contract = Contract.query.filter(Contract.contract_no == contract_no).first()
        refund = Refund.query.filter(Refund.id==int(refund_id),Refund.contract_id.is_(None)).first()
        if not contract or not refund:
            return {'isSucceed': 500, 'message': '未找到合同或还款流水'}
        refund.contract_id = contract.id
        contract.remain_sum+=refund.amount
        contract.is_dealt = 1
        contract.refund_sum+=refund.amount
        db.session.add(contract)
        db.session.add(refund)
        db.session.commit()
        self.update_contract(contract.contract_no)
        return {'isSucceed': 200, 'message': '冲账成功'}


    def update_contract(self,contract_no):
        contract = Contract.query.filter(Contract.contract_no == contract_no).first()
        commit_plan = CommitRefund.query.filter(CommitRefund.contract_id == contract.id, CommitRefund.is_valid == 1,
                                                CommitRefund.is_settled == 0).first()
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
            overtime_plans = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,
                                                      tRefundPlan.is_settled == 0,
                                                      tRefundPlan.deadline < datetime.datetime.now()).all()
            if not overtime_plans:  # 第二步检查是否还有逾期未处理
                now = datetime.datetime.now()
                end_time = datetime.datetime(now.year, now.month, now.day + 1, 0, 0, 0)
                refund_plan = tRefundPlan.query.filter(tRefundPlan.contract_id == contract.id,
                                                       tRefundPlan.is_settled == 0,
                                                       tRefundPlan.deadline == end_time).first()
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
    def search_refund(self,file_id=None,is_match=None,refund_name=None,create_time=None,page=None):
        def get_query():
            query = Refund.query
            if file_id:
                query = query.filter(Refund.file_id == file_id)
            if refund_name:
                query = query.filter(Refund.refund_name == refund_name)
            if is_match == '0':
                query = query.filter(Refund.contract_id.is_(None))
            if is_match == '1':
                query = query.filter(Refund.contract_id != '')
            if create_time:
                start_date = DateStrToDate(create_time, 0, 0, 0)
                end_date = DateStrToDate(create_time, 23, 59, 59)
                query = query.filter(Refund.create_time.between(start_date,end_date))
            else:
                start_date = datetime.datetime(1990, 1, 1)
                end_date = datetime.datetime.now()
                query = query.filter(Refund.create_time.between(start_date,end_date))
            return query.order_by(Refund.create_time.desc()).all()

        search_refunds = get_query()
        num = len(search_refunds)
        if page:
            page=int(page)
        else:page = 1

        if (page-1)*10+10<=num:
            page_refunds = search_refunds[(page-1)*10:(page-1)*10+10]
        elif (page-1)*10<=num:
            page_refunds = search_refunds[(page-1)*10:]
        else:
            page_refunds = []
        search_refund_list = []
        if page_refunds:
            for refund in page_refunds:
                refundsStr = {'way': refund.method, 'refundTime': refund.refund_time.strftime("%Y-%m-%d %H:%M:%S"),
                              'create_time': refund.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                              'refund_name': refund.refund_name, 'file_id': refund.file_id,
                              'contract_id': refund.contract_id, 'card_id': refund.card_id,
                              'amount': "%.2f" % (refund.amount / 100)}
                search_refund_list.append(refundsStr)
            result_dic = {'isSucceed': 200, 'search_refund_list': search_refund_list, 'message': '查询还款流水成功！','num':num}
        else:
            result_dic = {'isSucceed': 200, 'search_refund_list': search_refund_list, 'message': '查询还款流水成功！','num':num}
        return  result_dic


#计算每日逾期费用
def count_daily_delay():
    from .sqlhelper import get_delay_refund,update_plan_fee
    refunds = get_delay_refund()
    if refunds:
        for refund in refunds:
            pid = refund['id']
            contract_id = refund['contract_id']
            contract = Contract.query.filter(Contract.id == contract_id).first()
            contractAmt = contract.contract_amount #合同额
            now = datetime.datetime.now()
            delayDay = (now-refund['deadline']).days #逾期天数
            fee = countFee(contractAmt,delayDay)

            update_plan_fee(fee,delayDay, pid)
            #update_contract(is_dealt=0,is_settled=0,contract_id=contract_id)

#滞纳金算法
def countFee(contractAmt,delayDay):
    if contractAmt >= 10000:
        return delayDay*200
    else:
        return delayDay*100


#根据还款情况同步合同状态
def ontime_refunds():
    from .sqlhelper import ontime_refund,update_contract
    refunds = ontime_refund()
    if refunds:
        for refund in refunds:
            contract_id = refund['contract_id']
            print(contract_id)
            update_contract(is_dealt=0,is_settled=0,contract_id=contract_id)

#回滚失效的减免申请
def ontime_commits():
    from .sqlhelper import ontime_commit,update_commit,update_plan_by_commit
    commits = ontime_commit()
    if commits:
        for commit in commits:
            update_commit(is_valid=0,is_settled=0,result=1,commit_id=commit['id'])
            update_plan_by_commit(commit_id=commit['id'])





















# class DigitalExecute:



