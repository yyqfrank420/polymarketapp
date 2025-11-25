import sys
import os
from dotenv import load_dotenv

# Auto-detect project home (works for both local and PythonAnywhere)
project_home = os.path.dirname(os.path.abspath(__file__))

if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from .env file
load_dotenv(os.path.join(project_home, '.env'))

os.environ['FLASK_ENV'] = os.environ.get('FLASK_ENV', 'production')

from app import app as application