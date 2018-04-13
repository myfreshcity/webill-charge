#!/usr/bin/python
# -*- coding: UTF-8 -*-
from flask import render_template,jsonify,request,send_file,send_from_directory
from . import main
from .table_data_server import FileExecute,DataExecute
import json
from .. import config
from .back_server import TokenTest



# @main.route('/',methods=['GET','POST'])
# @login_required
# def index():
#     form=NameForm()
#     if form.validate_on_submit():
#         user=User.query.filter_by(username=form.name.data).first()
#         print(user)
#         if user is None:
#             user=User(username=form.name.data)
#             db.session.add(user)
#             db.session.commit()
#             session["known"]=False
#         else:
#             session["known"]=True
#         session['name']=form.name.data
#         return redirect(url_for('.index'))
#     return render_template('index.html', current_time=datetime.utcnow(),form=form,name=session.get("name"),known=session.get("known",False))
#下载计划文件



@main.route('/charge/plan/download',methods=['POST','GET'])
def download_plan():
    dictory = config['dev'].DOWNLOAD_FOLD
    filename = "refund_plan.xls"
    return send_from_directory(dictory,filename,as_attachment=True)

#下载流水文件
@main.route('/charge/refund/download',methods=['POST','GET'])
def download_refund():
    dictory = config['dev'].DOWNLOAD_FOLD
    filename = "refund.xls"
    return send_from_directory(dictory,filename,as_attachment=True)

#上传合同和还款计划书
@main.route('/charge/plan/upload',methods=['POST','GET'])
@TokenTest
def plan_upload():
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
def refund_upload():
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
@main.route('/charge/contract/select',methods=['POST'])
@TokenTest
def get_contract_deal():
    page = request.form.get('page')
    customer=request.form.get('customer')
    contract_no=request.form.get('contract_no')
    check_date=request.form.get('check_date')
    id_number=request.form.get('id_number')
    check_status=request.form.get('check_status')
    execute = DataExecute()
    result=execute.get_deal_refund(contract_no,customer,check_date,check_status,page,id_number)
    return result

#获取合同详细信息(对账详情，上半部分)
@main.route('/charge/contract/detail/get',methods=['POST'])
@TokenTest
def get_contract_detail():
    data = request.get_data()
    j_data = json.loads(data.decode())
    contract_no = j_data['contract_no']
    contract_id = j_data['contract_id']
    is_overtime  = j_data['is_overtime']
    execute = DataExecute()
    result = execute.contract_detail(contract_no,is_overtime,contract_id)
    return result


#获取未匹配流水
@main.route('/charge/refund/unlink/get',methods=['POST'])
@TokenTest
def unlinked_refund():
    page,customer,refund_date,range = request.form.get('page'),request.form.get('customer'),request.form.get('refund_date'),request.form.get('range')
    execute = DataExecute()
    result=execute.get_unlinked_refund(page,customer,refund_date,range)
    return result


#修改还款信息
@main.route('/charge/commit/create',methods=['POST'])
@TokenTest
def create_commit():
    contract_no = request.form.get('contract_no')
    user_id = request.form.get('user_id')
    amount = request.form.get('amount')
    commit = request.form.get('commit')
    type = request.form.get('type')
    discount_type = request.form.get('discount_type')
    execute = DataExecute()
    result = execute.create_commit(contract_no=contract_no,user_id=user_id,amount=amount,commit=commit,type=type,discount_type=discount_type)
    return result

#冲账
@main.route('/charge/refund/unlink/link',methods=['POST'])
@TokenTest
def link_refund():
    contract_no,user_id,refund_id = request.form.get('contract_no'),request.form.get('user_id'),request.form.get('refund_id')
    execute = DataExecute()
    result=  execute.link_refund_to_contract(contract_no,refund_id)
    return result

#协商还款审批
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
    execute = DataExecute()
    result = execute.get_commits(applyer=applyer,customer=customer,page=page)
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
    refund_name = request.form.get('refund_name')
    create_time = request.form.get('create_time')
    page = request.form.get('page')
    execute = DataExecute()
    result=execute.search_refund(file_id,is_match,refund_name,create_time,page)
    print(result)
    return jsonify(result)

@main.route('/test',methods=['POST','GET'])
def test():
    execute = DataExecute()
    result=execute.get_commits()
    return jsonify(result)






