#!/usr/bin/python
# -*- coding: UTF-8 -*-
from flask import render_template,jsonify,request,send_file,send_from_directory

from app.main.db_service import do_del_contract, do_refund_reset
from . import main
from .table_data_server import FileExecute,DataExecute
import json
from .. import config, app
from .utils import TokenTest, QueryForm

@main.route('/charge/plan/download',methods=['POST','GET'])
def download_plan():
    dictory = app.config['DOWNLOAD_FOLD']
    filename = "refund_plan.xls"
    return send_from_directory(dictory,filename,as_attachment=True)

#下载流水文件
@main.route('/charge/refund/download',methods=['POST','GET'])
def download_refund():
    dictory = app.config['DOWNLOAD_FOLD']
    filename = "refund.xls"
    return send_from_directory(dictory,filename,as_attachment=True)

#上传合同和还款计划书
@main.route('/charge/plan/upload',methods=['POST','GET'])
@TokenTest
def upload_plan():
    if request.method == 'GET':
        return render_template("upload.html")
    else:
        file = request.files['file']
        if file:
            execute = FileExecute(file,kind='plan')
            message=execute.execute_file()
        else:
            message ={'issucceed':500,'message':'未接收到文件'}
        return message

#上传还款流水表
@main.route('/charge/refund/upload',methods=['POST','GET'])
@TokenTest
def upload_refund():
    if request.method == 'GET':
        return render_template("upload.html")
    else:
        file = request.files['file']
        if file:
            execute = FileExecute(file,kind='refund')
            message=execute.execute_file()
        else:
            message ={'issucceed':500,'message':'未接收到文件'}
        return message

#对账处理
@main.route('/charge/contract/get',methods=['POST'])
@TokenTest
def get_contract():
    all,page,customer,contract_no,check_date,check_status = request.form.get('all'),request.form.get('page'),request.form.get('customer'),request.form.get('contract_no'),request.form.get('upload_time'),request.form.get('check_status')
    execute = DataExecute()
    result=execute.unse_get_contract(contract_no,customer,check_date,page,all)
    return result

#对账处理/贷款列表
@main.route('/charge/contract/del',methods=['POST'])
@TokenTest
def del_contract():
    cid = request.form.get('cid')
    result = do_del_contract(cid)
    return result

#对账处理/贷款列表
@main.route('/charge/contract/select',methods=['POST'])
@TokenTest
def get_contract_deal():
    execute = DataExecute()
    query = QueryForm()
    query.page = request.form.get('page')
    query.customer = request.form.get('customer')
    query.shop = request.form.get('shop')
    query.sale_person = request.form.get('sale_person')
    query.contract_no = request.form.get('contract_no')
    query.repay_date = request.form.get('repay_date')
    query.id_number = request.form.get('id_number')
    query.is_dealt = request.form.get('is_dealt')
    query.is_settled = request.form.get('is_settled')
    query.file_id = request.form.get('file_id')
    query.from_yu_day = request.form.get('from_yu_day')
    query.to_yu_day = request.form.get('to_yu_day')

    result = execute.get_deal_refund(query)
    return result

#获取合同详细信息(对账详情，上半部分)
@main.route('/charge/contract/detail/get',methods=['POST'])
@TokenTest
def get_contract_detail():
    data = request.get_data()
    j_data = json.loads(data.decode())
    contract_id = j_data['contract_id']
    execute = DataExecute()
    result = execute.contract_detail(contract_id)
    return result


#获取未匹配流水
@main.route('/charge/refund/unlink/get',methods=['POST'])
@TokenTest
def unlinked_refund():
    page,customer,refund_date,range = request.form.get('page'),request.form.get('customer'),request.form.get('refund_date'),request.form.get('range')
    execute = DataExecute()
    result=execute.get_unlinked_refund(page,customer,refund_date,range)
    return result

#还款流水重新匹配
@main.route('/charge/refund/rematch',methods=['POST'])
@TokenTest
def rematch_refund():
    refund_id = request.form.get('refund_id')
    execute = DataExecute()
    result=  execute.refund_re_match(refund_id)
    return result

@main.route('/charge/refund/reset',methods=['POST'])
@TokenTest
def reset_refund():
    refund_id = int(request.form.get('refund_id'))
    result=  do_refund_reset(refund_id)
    return result


#修改还款信息
@main.route('/charge/commit/create',methods=['POST'])
@TokenTest
def create_commit():
    contract_no = request.form.get('contract_no')
    user_id = request.form.get('user_id')
    pay_amt = request.form.get('pay_amt')
    amount = request.form.get('amount')
    remark = request.form.get('commit')
    type = request.form.get('type')
    discount_type = request.form.get('discount_type')
    execute = DataExecute()
    result = execute.create_commit(contract_no,user_id,pay_amt,amount,remark,type,discount_type)
    return result

#冲账
@main.route('/charge/refund/unlink/link',methods=['POST'])
@TokenTest
def link_refund():
    contract_no,user_id,refund_id,contract_id = request.form.get('contract_no'),request.form.get('user_id'),request.form.get('refund_id'),request.form.get('contract_id')
    execute = DataExecute()
    result=  execute.link_refund_to_contract(contract_no,contract_id,refund_id)
    return result

#对账审核
@main.route('/charge/commit/approve',methods=['POST'])
@TokenTest
def approve_commit():
    user_id,comment_id,result,comments = request.form.get('user_id'),request.form.get('commit_id'),request.form.get('result'),request.form.get('comments')
    execute = DataExecute()
    result=execute.approve_commit(comment_id,result,user_id,comments)
    return result

#协商还款列表
@main.route('/charge/commit/get',methods=['POST'])
@TokenTest
def get_commit():
    applyer,customer,page = request.form.get('applyer'),request.form.get('customer'),request.form.get('page')
    shop = request.form.get('shop')
    execute = DataExecute()
    result = execute.get_commits(applyer=applyer,customer=customer,shop=shop,page=page)
    return result

#协商还款详情
@main.route('/charge/commit/detail/get',methods=['POST'])
@TokenTest
def get_commit_detail():
    data = request.get_data()
    j_data = json.loads(data.decode())
    commit_id = j_data['commit_id']
    execute = DataExecute()
    result=execute.get_commit_detail(commit_id)
    return result

#按门店，渠道获取最新时间
@main.route('/charge/refund/newest',methods=['GET'])
def get_newest_date():
    execute = DataExecute()
    result=execute.get_newest_date()
    return jsonify(result)

#查询还款流水
@main.route('/charge/refund/search',methods=['POST'])
@TokenTest
def search_refund():
    file_id = request.form.get('file_id')
    is_match = request.form.get('is_match')
    shop = request.form.get('shop')
    refund_name = request.form.get('refund_name')
    refund_time = request.form.get('refund_time')
    page = request.form.get('page')
    execute = DataExecute()
    result=execute.search_refund(file_id,is_match,refund_name,refund_time,shop,page)
    return jsonify(result)

@main.route('/test',methods=['POST','GET'])
def test():
    execute = DataExecute()
    result=execute.get_commits()
    return jsonify(result)






