import logging

from flask import current_app

import config
from app import app, celery
from app.main.match_engine import MatchEngine
from app.models import *


@celery.task
def sendmail(mail):
    import time
    print('sending mail to %s...' % mail['to'])
    time.sleep(2.0)
    print('mail sent.')

@celery.task
def batch_match_refund(file_id):
    data_list = Repayment.query.filter(Repayment.file_id==file_id).order_by(Repayment.refund_time.asc()).all()
    for refund in data_list:
        engine = MatchEngine()
        engine.match_by_refund(refund)