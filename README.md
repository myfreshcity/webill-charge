本项目为微账房对账项目

启动程序
 python manage.py runserver -H localhost

virtualenvs 配置：
 virtualenv -p /usr/local/bin/python3 venv

激活 virtualenvs：
 source venv/bin/activate

退出 virtualenvs：
 deactivate

生产环境的启动
 venv/bin/uwsgi --ini uwsgi.ini | tail -f uwsgi.log

 程序终止：
 kill -HUP `cat uwsgi.pid`
 venv/bin/uwsgi --reload uwsgi.pid | tail -f uwsgi.log

 安装依赖
pip install -r requirements.txt


安装
  pip install jupyter
调试工具
   jupyter notebook

Celery 启动命令
   venv/bin/celery -A app.celery worker --loglevel=info


上传文件夹赋权
   chmod -R 766 Uploads


生产环境：
该项目目前在window7生产环境下运行，使用Apache启动
直接Apache开启项目访问项目首页即可以启动


#对账逻辑说明：


1）减免申请第二天自动失效。
2）每期本息还清后，滞纳金不再滚动计算。
3）客户多期未还，冲账时，先充每期本息，余额再逐期充滞纳金。
4）对于客户多还的钱，包括提前还款的，人工核对后冲账。