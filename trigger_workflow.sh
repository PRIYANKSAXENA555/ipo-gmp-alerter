#!/bin/bash
# Script to trigger GitHub Actions workflow
# Run this with cron on your local machine

cd /Users/prathikr/workspace/gmp-scraper
gh workflow run "Daily IPO Check"
echo "$(date): Triggered IPO check workflow"
