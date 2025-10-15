# 🚀 Deploy to PythonAnywhere from GitHub

## Quick Deploy (10 Minutes)

### Step 1: Push to GitHub (2 min)

```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit: YourGroupPredictionMarket waitlist"

# Create repo on GitHub, then push
git remote add origin https://github.com/yourusername/yourrepo.git
git branch -M main
git push -u origin main
```

### Step 2: Clone on PythonAnywhere (3 min)

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Open a **Bash console**
3. Clone your repository:

```bash
cd ~
git clone https://github.com/yourusername/yourrepo.git TVB_Workshops
cd TVB_Workshops
```

### Step 3: Setup (2 min)

```bash
# Install dependencies
pip3.10 install --user -r requirements.txt

# Initialize database
python3.10 -c "from waitinglist_app import init_db; init_db()"

# Verify
ls -lh waitinglist.db
```

### Step 4: Configure Web App (3 min)

1. Go to **Web** tab → **Add a new web app**
2. Choose **Manual configuration** → **Python 3.10**
3. Click the **WSGI configuration file** link
4. **Delete all content** and paste (replace `yourusername`):

```python
import sys
import os

project_home = '/home/yourusername/TVB_Workshops'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'

from waitinglist_app import app as application
```

5. **Save** the file

6. In **Static files** section, add:
   - URL: `/static/`
   - Directory: `/home/yourusername/TVB_Workshops/static/`

7. Click **Reload** button

### Step 5: Go Live! ✅

Visit: `https://yourusername.pythonanywhere.com`

---

## Update Your Site

When you make changes:

```bash
# On PythonAnywhere Bash console
cd ~/TVB_Workshops
git pull origin main

# If you changed Python code
# Go to Web tab → click Reload
```

---

## Database Management

```bash
# View stats
python3.10 db_manager.py stats

# Recent registrations
python3.10 db_manager.py recent 10

# Export CSV
python3.10 db_manager.py export

# Backup
python3.10 db_manager.py backup
```

---

## Troubleshooting

**Error logs:**
```bash
tail -50 /var/log/yourusername.pythonanywhere.com.error.log
```

**Reset database:**
```bash
cd ~/TVB_Workshops
rm waitinglist.db
python3.10 -c "from waitinglist_app import init_db; init_db()"
# Then reload web app
```

---

## That's It! 🎉

Your waitlist is live. Share your URL and start collecting emails!

