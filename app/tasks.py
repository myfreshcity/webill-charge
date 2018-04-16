from celery import Celery
from celery.schedules import crontab

from app import celery, app, create_app
from app.main.match_engine import match_by_refund
from app.models import *


@celery.task
def sendmail(mail):
    import time
    print('sending mail to %s...' % mail['to'])
    time.sleep(2.0)
    print('mail sent.')

@celery.task
def batch_match_refund(file_id):
    app = create_app("dev")
    with app.app_context():
        app.logger.debug('begin matching ...')
        data_list = Refund.query.filter(Refund.file_id==file_id).all()
        for refund in data_list:
            match_by_refund(refund)