#!/usr/bin/python
# -*- coding: UTF-8 -*-
from . import db,login_manager,mdb
from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import UserMixin
import datetime

class Permission:
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__='roles'
    id=db.Column(db.Integer(),primary_key=True)
    name=db.Column(db.String(64),unique=True)
    default=db.Column(db.Boolean,default=False,index=True)
    permissions=db.Column(db.Integer)
    users = db.relationship("User", backref='role',lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles={
            'User':(Permission.FOLLOW|Permission.COMMENT|Permission.WRITE_ARTICLES,True),
            'Moderator':(Permission.FOLLOW|Permission.COMMENT|Permission.WRITE_ARTICLES|
                         Permission.MODERATE_COMMENTS,False),
            'Administrator':(0xff,False)}
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role=Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles [r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return "<Role %s>"%self.name

class User(UserMixin,db.Model):
    __tablename__='users'
    id=db.Column(db.Integer(),primary_key=True)
    email=db.Column(db.String(64),unique=True,index=True)
    username=db.Column(db.String(64),unique=True)
    password_hash = db.Column(db.String(128))
    role_id = db.Column(db.Integer(), db.ForeignKey("roles.id"))
    #
    # def __init__(self,**kwargs):
    #     super(User,self).__init__(**kwargs)
    #     if self.role is None:
    #         if self.email == current_app.config["FLASKY_ADMIN"]:
    #             self.role = Role.query.filter_by(permission=0xff).first()
    #         if self.email is None:
    #             self.role = Role.query.filter_by(default=True).first()

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self,password):
        self.password_hash=generate_password_hash(password=password)
    def verify_password(self,password):
        return check_password_hash(self.password_hash,password=password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Contract(db.Model):
    __tablename__='t_contract'
    id = db.Column(db.Integer(), primary_key=True)
    contract_no = db.Column(db.VARCHAR(50),unique=True)
    customer = db.Column(db.VARCHAR(20),default='')
    mobile_no = db.Column(db.VARCHAR(20),default='')
    id_number = db.Column(db.VARCHAR(20),default='')
    shop = db.Column(db.VARCHAR(20),default='')
    tensor = db.Column(db.Integer,default=0)
    delayed_day = db.Column(db.Integer,default=0)
    contract_amount = db.Column(db.Integer,default=0)
    loan_amount = db.Column(db.Integer,default=0)
    loan_date = db.Column(db.DateTime)
    remain_sum = db.Column(db.Integer,default=0)
    refund_sum  =db.Column(db.Integer,default=0)
    is_settled = db.Column(db.Integer,default=0)
    is_dealt = db.Column(db.Integer,default=0)
    file_id = db.Column(db.Integer,default=0)
    create_time = db.Column(db.DateTime)
    refund_plans = db.relationship("ContractRepay",backref='contract')
    refund = db.relationship('Repayment', backref='contract')
    commit = db.relationship('CommitInfo',backref='contract')

    def __repr__(self):
        return "<Contract %s>"%self.contract_no

class ContractRepay(db.Model):
    __tablename__ = 't_contract_repay'
    id = db.Column(db.Integer(), primary_key=True)
    contract_id = db.Column(db.ForeignKey('t_contract.id'))
    deadline = db.Column(db.DateTime)
    file_id = db.Column(db.ForeignKey('t_upload_file.id'))
    tensor = db.Column(db.Integer,default=0)
    delay_day = db.Column(db.Integer,default=0)
    amt = db.Column(db.Integer,default=0)
    fee = db.Column(db.Integer,default=0)
    actual_amt = db.Column(db.Integer,default=0)
    actual_fee = db.Column(db.Integer,default=0)
    principal = db.Column(db.Integer,default=0)
    interest = db.Column(db.Integer,default=0)
    is_settled = db.Column(db.Integer,default=0)
    settled_date = db.Column(db.DateTime)
    settled_by_commit = db.Column(db.ForeignKey('t_commit_info.id'))


    def __repr__(self):
        return "<ContractRepay %s>"%self.id


class UploadFile(db.Model):
    __tablename__ = 't_upload_file'
    id = db.Column(db.Integer(), primary_key=True)
    file_name = db.Column(db.VARCHAR(50))
    file_kind = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime)
    file_dir = db.Column(db.VARCHAR(255))
    is_valid = db.Column(db.Integer,default=1)

    def __repr__(self):
        return "<File %s>"%self.file_name


class Repayment(db.Model):
    __tablename__='t_repayment'
    id = db.Column(db.Integer(), primary_key=True)
    file_id = db.Column(db.ForeignKey('t_upload_file.id'))
    contract_id = db.Column(db.ForeignKey('t_contract.id'))
    refund_name = db.Column(db.VARCHAR(20))
    refund_time = db.Column(db.DateTime)
    method = db.Column(db.VARCHAR(20))
    amount = db.Column(db.Integer)
    remain_amt = db.Column(db.Integer)
    bank = db.Column(db.VARCHAR(30))
    card_id = db.Column(db.Integer)
    t_status = db.Column(db.Integer,default=0)
    create_time = db.Column(db.DateTime,default=datetime.datetime.now())

    def __repr__(self):
        return "<Repayment %s>"%self.refund_name


class CommitInfo(db.Model):
    __tablename__='t_commit_info'
    id = db.Column(db.Integer(), primary_key=True)
    contract_id = db.Column(db.ForeignKey('t_contract.id'))
    apply_date = db.Column(db.DateTime)
    applyer = db.Column(db.VARCHAR(20))
    type = db.Column(db.Integer)
    discount_type = db.Column(db.Integer)
    amount = db.Column(db.Integer,default=0)
    remain_amt = db.Column(db.Integer,default=0)
    deadline = db.Column(db.DateTime)
    approve_date = db.Column(db.DateTime)
    approver = db.Column(db.VARCHAR(20))
    approve_remark = db.Column(db.VARCHAR)
    result = db.Column(db.Integer)
    is_valid = db.Column(db.Integer)
    remark = db.Column(db.TEXT)
    create_time = db.Column(db.DateTime)
    plans = db.relationship('ContractRepay',backref='commit')

class FundMatchLog(db.Model):
    __tablename__='t_fund_match_log'
    id = db.Column(db.Integer(), primary_key=True)
    match_type = db.Column(db.Integer, default=0)
    plan_id = db.Column(db.Integer,default=0)
    fund_id = db.Column(db.Integer,default=0)
    contract_id = db.Column(db.Integer,default=0)
    amount = db.Column(db.Integer,default=0)
    f_remain_amt = db.Column(db.Integer,default=0)
    p_remain_amt = db.Column(db.Integer,default=0)
    remark = db.Column(db.VARCHAR(2000))
    t_status = db.Column(db.Integer,default=0)
    created_time = db.Column(db.DateTime,default=datetime.datetime.now())




