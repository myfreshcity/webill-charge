����ĿΪ΢�˷�������Ŀ

��������
 python manage.py runserver -H localhost

virtualenvs ���ã�
 virtualenv -p /usr/local/bin/python3 venv

���� virtualenvs��
 source venv/bin/activate

�˳� virtualenvs��
 deactivate

��������������
 venv/bin/uwsgi --ini uwsgi.ini | tail -f uwsgi.log

 ������ֹ��
 kill -HUP `cat uwsgi.pid`
 venv/bin/uwsgi --reload uwsgi.pid | tail -f uwsgi.log

 ��װ����
pip install -r requirements.txt

����������
����ĿĿǰ��window7�������������У�ʹ��Apache����
ֱ��Apache������Ŀ������Ŀ��ҳ����������