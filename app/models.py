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
    customer = db.Column(db.VARCHAR(20))
    mobile_no = db.Column(db.VARCHAR(20))
    id_number = db.Column(db.VARCHAR(20))
    shop = db.Column(db.VARCHAR(20))
    tensor = db.Column(db.Integer)
    contract_amount = db.Column(db.Integer)
    loan_amount = db.Column(db.Integer)
    loan_date = db.Column(db.DateTime)
    remain_sum = db.Column(db.Integer,default=0)
    refund_sum  =db.Column(db.Integer,default=0)
    is_settled = db.Column(db.Integer,default=0)
    is_dealt = db.Column(db.Integer,default=0)
    file_id = db.Column(db.Integer)
    create_time = db.Column(db.DateTime)
    refund_plans = db.relationship("tRefundPlan",backref='contract')
    refund = db.relationship('Refund', backref='contract')
    commit = db.relationship('CommitRefund',backref='contract')

    def __repr__(self):
        return "<Contract %s>"%self.contract_no

class tRefundPlan(db.Model):
    __tablename = 't_refund_plan'
    id = db.Column(db.Integer(), primary_key=True)
    contract_id = db.Column(db.ForeignKey('t_contract.id'))
    deadline = db.Column(db.DateTime)
    file_id = db.Column(db.ForeignKey('t_upload_file.id'))
    tensor = db.Column(db.Integer)
    delay_day = db.Column(db.Integer)
    fee = db.Column(db.Integer)
    actual_amt = db.Column(db.Integer)
    actual_fee = db.Column(db.Integer)
    principal = db.Column(db.Integer)
    interest = db.Column(db.Integer)
    is_settled = db.Column(db.Integer,default=0)
    settled_date = db.Column(db.DateTime)
    settled_by_commit = db.Column(db.ForeignKey('t_commit_refund.id'))


    def __repr__(self):
        return "<RefundPlan %s>"%self.id


class UploadFile(db.Model):
    __tablename__ = 't_upload_file'
    id = db.Column(db.Integer(), primary_key=True)
    file_name = db.Column(db.VARCHAR(50))
    file_kind = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime)
    file_dir = db.Column(db.VARCHAR(255))
    is_valid = db.Column(db.Integer,default=1)
    trefundplan = db.relationship('tRefundPlan',backref='file')
    refund = db.relationship('Refund',backref='file')

    def __repr__(self):
        return "<File %s>"%self.file_name


class Refund(db.Model):
    __tablename__='t_refund'
    id = db.Column(db.Integer(), primary_key=True)
    file_id = db.Column(db.ForeignKey('t_upload_file.id'))
    contract_id = db.Column(db.ForeignKey('t_contract.id'))
    refund_name = db.Column(db.VARCHAR(20))
    refund_time = db.Column(db.DateTime)
    method = db.Column(db.VARCHAR(20))
    amount = db.Column(db.Integer)
    bank = db.Column(db.VARCHAR(30))
    card_id = db.Column(db.Integer)
    create_time = db.Column(db.DateTime,default=datetime.datetime.now())

    def __repr__(self):
        return "<Refund %s>"%self.refund_name


class CommitRefund(db.Model):
    __tablename__='t_commit_refund'
    id = db.Column(db.Integer(), primary_key=True)
    contract_id = db.Column(db.ForeignKey('t_contract.id'))
    apply_date = db.Column(db.DateTime)
    applyer = db.Column(db.VARCHAR(20))
    type = db.Column(db.Integer)
    discount_type = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    deadline = db.Column(db.DateTime)
    approve_date = db.Column(db.DateTime)
    approver = db.Column(db.VARCHAR(20))
    approve_remark = db.Column(db.VARCHAR)
    result = db.Column(db.Integer)
    is_valid = db.Column(db.Integer)
    remark = db.Column(db.TEXT)
    plans = db.relationship('tRefundPlan',backref='commit')
    create_time = db.Column(db.DateTime)






