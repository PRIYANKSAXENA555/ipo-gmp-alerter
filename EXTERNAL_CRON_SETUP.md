# External Cron Service Setup

Since GitHub Actions scheduled workflows are unreliable on free accounts, we'll use a free external cron service.

## 🎯 **Setup Steps:**

### **1. Get GitHub Personal Access Token**
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (Full control of private repositories)
4. Copy the token (starts with `ghp_`)

### **2. Set up cron-job.org (Free)**
1. Go to: https://cron-job.org
2. Create free account
3. Click "Create cronjob"
4. Fill in:
   - **Title**: `IPO GMP Daily Check`
   - **Address**: `https://api.github.com/repos/PratLegacy/ipo-gmp-alerter/dispatches`
   - **Method**: `POST`
   - **Headers**:
     ```
     Authorization: token YOUR_GITHUB_TOKEN
     Accept: application/vnd.github.v3+json
     Content-Type: application/json
     ```
   - **Body**:
     ```json
     {"event_type": "run-ipo-check"}
     ```
   - **Schedule**: `0 9 * * *` (9:00 AM IST daily)
   - **Timezone**: `Asia/Kolkata`

### **3. Alternative: EasyCron (Free)**
1. Go to: https://www.easycron.com
2. Create free account (1 cron job free)
3. Similar setup as above

## 🎯 **Benefits:**
- ✅ **100% reliable** - External service triggers GitHub Actions
- ✅ **Free** - No cost involved
- ✅ **Precise timing** - Runs exactly when scheduled
- ✅ **No GitHub limitations** - Works with free GitHub accounts

## 🔧 **Manual Trigger:**
You can still trigger manually:
```bash
gh workflow run "External Cron Triggered IPO Check"
```

## 📱 **Result:**
- **Daily at 9:15 AM IST**: Telegram message with IPO opportunities
- **Reliable delivery**: No more missed runs
- **Free solution**: No GitHub Pro needed
