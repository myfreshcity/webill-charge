import logging

from flask import current_app

import config
from app import app, celery
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
    app.debug_log_format = '[%(levelname)s] %(message)s'
    app.debug = True
    app.logger.debug('begin matching ...')

    config = current_app.config
    LOG_FILENAME = config.get('LOG_FILENAME')

    handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=config.get('LOG_FILESIZE'), backupCount=20,
                                                   encoding='UTF-8')
    handler.setLevel(logging.DEBUG)
    logging_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s - %(lineno)s - %(message)s')
    handler.setFormatter(logging_format)
    app.logger.addHandler(handler)


    data_list = Repayment.query.filter(Repayment.file_id==file_id).order_by(Repayment.refund_time.asc()).all()
    for refund in data_list:
        match_by_refund(refund)