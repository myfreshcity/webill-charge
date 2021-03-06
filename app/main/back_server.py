#!/usr/bin/python
# -*- coding: UTF-8 -*-
import re,datetime,requests,json
from flask import request,jsonify
from functools import wraps


def DateStrToDate(DateString,hour=0,minute=0,seconds=0):
    date_set = re.findall('(.+)-(.+)-(.+)', DateString)
    date = datetime.datetime(int(date_set[0][0]), int(date_set[0][1]), int(date_set[0][2]), int(hour),
                                   int(minute),int(seconds))
    return date


#token验证
def TokenTest(func):
    @wraps(func)
    def outer(*args,**kwargs):
        from .. import config
        if config['dev'].TOKEN_TEST_BUTTON:
            token = request.headers.get('token')
            #token = 'eyJhbGciOiJIUzI1NiJ9.eyJqdGkiOiIxNTEyMTE5MzE0MCIsImlhdCI6MTUyMTcwNzY0Nywic3ViIjoibW9iaWxlTm8iLCJpc3MiOiJtbWgiLCJleHAiOjE1MjE3MDk0NDd9.GmYl_YFH8xGiUfWpBpJnFQhzl-WB9MfKQgwnc0M4TTk'
            req = requests.post(url=config['dev'].TOKEN_TEST_URL,data=json.dumps({'token':token}))
            message = req.json()
            print(message)
            if int(message['result'])!=2:
                result= {'isSucceed':500,'message':message['message']}
            else:
                result = func(*args,**kwargs)
                if isinstance(result,dict):
                    result['token']=message['token']
            return jsonify(result)
        else:
            result = func(*args, **kwargs)
            if isinstance(result,dict):
                return jsonify(result)
            return result
    return outer