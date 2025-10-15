"""
WSGI configuration for PythonAnywhere deployment
Copy this content to your PythonAnywhere WSGI configuration file
Path: /var/www/<yourusername>_pythonanywhere_com_wsgi.py
"""

import sys
import os

# Add your project directory to the sys.path
# IMPORTANT: Replace 'yourusername' with your actual PythonAnywhere username
project_home = '/home/yourusername/TVB_Workshops'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment to production
os.environ['FLASK_ENV'] = 'production'

# Import the Flask app
from waitinglist_app import app as application

# This is what PythonAnywhere will use
# Note: PythonAnywhere expects 'application', not 'app'

