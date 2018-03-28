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

#上传还款计划书
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

#获取未完成合同表单
@main.route('/charge/contract/get',methods=['POST'])
@TokenTest
def get_contract():
    all,page,customer,contract_no,check_date,check_status = request.form.get('all'),request.form.get('page'),request.form.get('customer'),request.form.get('contract_no'),request.form.get('upload_time'),request.form.get('check_status')
    execute = DataExecute()
    result=execute.unse_get_contract(contract_no,customer,check_date,page,all)
    return result


#获取合同详细信息
@main.route('/charge/contract/detail/get',methods=['POST'])
@TokenTest
def get_contract_detail():
    data = request.get_data()
    j_data = json.loads(data.decode())
    contract_no = j_data['contract_no']
    is_overtime  = j_data['is_overtime']
    execute = DataExecute()
    result = execute.contract_detail(contract_no,is_overtime=is_overtime)
    return result


#获取未匹配流水
@main.route('/charge/refund/unlink/get',methods=['POST'])
@TokenTest
def unlinked_refund():
    page,customer,refund_date,range = request.form.get('page'),request.form.get('customer'),request.form.get('refund_date'),request.form.get('range')
    execute = DataExecute()
    result=execute.get_unlinked_refund(page,customer,refund_date,range)
    return result


#创建协商还款计划
@main.route('/charge/commit/create',methods=['POST'])
@TokenTest
def create_commit():
    contract_no,user_id,amount,deadline,commit,type = request.form.get('contract_no'),request.form.get('user_id'), \
                                                             request.form.get('amount'),request.form.get('deadline'),request.form.get('commit'),request.form.get('type')
    execute = DataExecute()
    result = execute.create_commit(contract_no=contract_no,user_id=user_id,amount=amount,deadline=deadline,commit=commit,type=type)
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

@main.route('/test',methods=['POST','GET'])
def test():
    execute= DataExecute()
    execute.test()
    return jsonify({'is':1})






