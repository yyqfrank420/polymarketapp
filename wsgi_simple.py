import sys
import os

project_home = '/home/yangyuqingfrank/TVB_Workshops'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'

from waitinglist_app import app as application
