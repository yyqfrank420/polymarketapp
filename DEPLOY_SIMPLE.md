# 🚀 Simple PythonAnywhere Deployment

## 1. Update code on PythonAnywhere
```bash
cd ~/TVB_Workshops
git pull origin main
```

## 2. Configure Web App
1. **Web tab** → **Add new web app** → **Manual config** → **Python 3.10**
2. **WSGI file** - Delete all content, paste:
```python
import sys
import os

project_home = '/home/yangyuqingfrank/TVB_Workshops'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'

from waitinglist_app import app as application
```

3. **Static files** - Add:
   - URL: `/static/`
   - Directory: `/home/yangyuqingfrank/TVB_Workshops/static/`

4. **Click Reload**

## 3. Done! 
Your app will be live at: `https://yangyuqingfrank.pythonanywhere.com`

**Features:**
- ✅ Futura landing page
- ✅ Premium subscription button (€67.67/month)
- ✅ Stripe integration working
- ✅ No environment variables needed

**Test with card:** `4242 4242 4242 4242`
