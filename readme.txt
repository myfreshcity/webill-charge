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

生产环境：
该项目目前在window7生产环境下运行，使用Apache启动
直接Apache开启项目访问项目首页即可以启动