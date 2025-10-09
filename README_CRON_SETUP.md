# Free Cron Service Setup

Since GitHub Actions scheduled workflows can be unreliable, here's how to set up a free external cron service:

## Option 1: cron-job.org (Free)

1. Go to https://cron-job.org
2. Create a free account
3. Create a new cron job:
   - **URL**: `https://api.github.com/repos/PratLegacy/ipo-gmp-alerter/actions/workflows/daily-ipo-check.yml/dispatches`
   - **Method**: POST
   - **Headers**: 
     - `Authorization: token YOUR_GITHUB_TOKEN`
     - `Accept: application/vnd.github.v3+json`
   - **Body**: `{"ref":"main"}`
   - **Schedule**: `0 9 * * *` (9:00 AM IST daily)

## Option 2: EasyCron (Free)

1. Go to https://www.easycron.com
2. Create free account (1 cron job free)
3. Set up similar webhook trigger

## Option 3: Local Cron (Your Computer)

Add to your crontab:
```bash
0 9 * * * cd /Users/prathikr/workspace/gmp-scraper && gh workflow run "Daily IPO Check"
```

## GitHub Token Setup

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` permissions
3. Use this token in the cron service
