# 🚀 Deploy to PythonAnywhere - Complete Guide

## Quick Deploy (10 Minutes)

### Step 1: Sign Up (2 min)

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com)
2. Click **"Start running Python online in less than a minute!"**
3. Sign up for a **free Beginner account**
4. Verify your email
5. Log in

---

### Step 2: Open Bash Console (1 min)

1. Once logged in, click **"Consoles"** tab (top menu)
2. Click **"Bash"** under "Start a new console"
3. A terminal will open - this is where you'll run commands

---

### Step 3: Run Deployment Script (3 min)

Copy and paste this **ONE-LINE COMMAND** into the Bash console:

```bash
curl -sSL https://raw.githubusercontent.com/yyqfrank420/polymarketapp/main/pythonanywhere_deploy.sh | bash
```

This will:
- ✅ Clone your repository from GitHub
- ✅ Install all dependencies
- ✅ Initialize the database
- ✅ Set up file permissions
- ✅ Test the setup

**Wait for it to complete** - you'll see a success message with next steps.

---

### Step 4: Configure Web App (4 min)

After the script finishes, follow the instructions it displays:

#### A. Create Web App

1. Click **"Web"** tab (top menu)
2. Click **"Add a new web app"**
3. Click **"Next"** (domain name confirmation)
4. Choose **"Manual configuration"**
5. Select **"Python 3.10"**
6. Click **"Next"**

#### B. Configure WSGI File

1. On the Web tab, find **"Code"** section
2. Click on the **WSGI configuration file** link (blue text)
3. **DELETE ALL existing content** in the file
4. **Paste this** (the script will show your username):

```python
import sys
import os

project_home = '/home/YOURUSERNAME/TVB_Workshops'  # Replace YOURUSERNAME
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['FLASK_ENV'] = 'production'

from waitinglist_app import app as application
```

5. **IMPORTANT**: Replace `YOURUSERNAME` with your actual PythonAnywhere username
6. Click **"Save"** (top right)

#### C. Configure Static Files

1. Back on the **Web** tab, scroll to **"Static files"** section
2. Click **"Enter URL"** and type: `/static/`
3. Click **"Enter path"** and type: `/home/YOURUSERNAME/TVB_Workshops/static/`
4. (Replace `YOURUSERNAME` with your actual username)

#### D. Set Source Code Path

1. In **"Code"** section, find **"Source code"**
2. Click the path and change it to: `/home/YOURUSERNAME/TVB_Workshops`
3. Find **"Working directory"** and set it to: `/home/YOURUSERNAME/TVB_Workshops`

#### E. Reload Web App

1. Scroll to the top of the Web tab
2. Click the big green **"Reload yourusername.pythonanywhere.com"** button
3. Wait a few seconds

---

### Step 5: Visit Your Site! 🎉

Click on your site link at the top of the Web tab, or go to:

```
https://yourusername.pythonanywhere.com
```

You should see your beautiful Polymarket-style waitlist landing page!

---

## 🧪 Test Your Site

### Homepage
- [ ] Page loads correctly
- [ ] Email form is visible
- [ ] Counter shows "0 people already on the waitlist"

### Submit Email
- [ ] Enter a test email
- [ ] Click "Join Waitlist"
- [ ] Success message appears
- [ ] Counter increments to 1

### Duplicate Prevention
- [ ] Try same email again
- [ ] Error message: "This email is already registered"

### Health Check
Visit: `https://yourusername.pythonanywhere.com/health`

Should show:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## 🛠️ Manage Your Database

In PythonAnywhere Bash console:

```bash
cd ~/TVB_Workshops

# View statistics
python3.10 db_manager.py stats

# View recent registrations
python3.10 db_manager.py recent 20

# Export to CSV
python3.10 db_manager.py export

# Backup database
python3.10 db_manager.py backup
```

---

## 🔄 Update Your Site

When you make changes to your code locally:

### On Your Computer:
```bash
git add .
git commit -m "Your update message"
git push origin main
```

### On PythonAnywhere:
```bash
cd ~/TVB_Workshops
git pull origin main
```

Then go to **Web tab** → Click **"Reload"**

---

## 🐛 Troubleshooting

### Site Not Loading?

**Check Error Log:**
- Go to Web tab
- Click **"Error log"** link
- Look for recent errors

**Or in Bash console:**
```bash
tail -50 /var/log/yourusername.pythonanywhere.com.error.log
```

### Database Issues?

**Reset Database:**
```bash
cd ~/TVB_Workshops
rm waitinglist.db
python3.10 -c "from waitinglist_app import init_db; init_db()"
```

Then reload web app.

### Static Files Not Loading?

**Check paths in Web tab:**
- URL should be: `/static/`
- Directory should be: `/home/yourusername/TVB_Workshops/static/`
- Make sure paths have correct username
- Reload web app

### Import Errors?

**Reinstall packages:**
```bash
cd ~/TVB_Workshops
pip3.10 install --user -r requirements.txt
```

Then reload web app.

---

## 📊 View Server Logs

```bash
# Error log
tail -50 /var/log/yourusername.pythonanywhere.com.error.log

# Server log
tail -50 /var/log/yourusername.pythonanywhere.com.server.log

# Access log
tail -50 /var/log/yourusername.pythonanywhere.com.access.log
```

---

## 🎯 Success Checklist

- [ ] PythonAnywhere account created
- [ ] Deployment script completed successfully
- [ ] Web app created (Manual configuration, Python 3.10)
- [ ] WSGI file configured with correct username
- [ ] Static files mapped
- [ ] Source code & working directory set
- [ ] Web app reloaded
- [ ] Site loads at https://yourusername.pythonanywhere.com
- [ ] Email form works
- [ ] Counter updates
- [ ] Duplicate email rejected
- [ ] Health check returns "healthy"

---

## 🎊 You're Live!

Your waitlist landing page is now live and collecting emails!

**Share your URL:**
```
https://yourusername.pythonanywhere.com
```

**Monitor registrations:**
```bash
python3.10 db_manager.py stats
```

---

**Need help? Check the error logs first, then see troubleshooting section above.**

Happy launching! 🚀

