#!/usr/bin/env python3
"""
IPO GMP Scraper - InvestorGain Final Complete Version
"""

import asyncio
import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import logging
import sys
import requests
import os
from datetime import datetime
import time
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
TELEGRAM_API_URL = "https://api.telegram.org/bot{}/sendMessage"
WEBSITE_URL = "https://www.investorgain.com/report/ipo-gmp-live/331/"


def send_telegram_alert(ipos: list, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        return False

    current_date = datetime.now().strftime("%B %d, %Y")

    if not ipos:
        message = f"📊 No IPO opportunities found today ({current_date})."
    else:
        message = f"🚀 <b>Daily IPO GMP (Sorted by Close Date)</b>\n📅 {current_date}\n\n"
        for ipo in ipos:
            # Add color dot based on GMP percentage
            gmp_percent = ipo['gmp_percent']
            if gmp_percent >= 20.0:
                color = "🟢"
            else:
                color = "🔴"
                
            message += f"{color} <b>{ipo['name']}</b>\n"
            message += f"💰 GMP: {ipo['gmp']} ({gmp_percent}%)\n"
            message += f"💵 Price: {ipo['price']}\n"
            message += f"📅 Open: {ipo['open']} | Close: {ipo['close']}\n\n"

    if len(message) > 4000:
        message = message[:3900] + "\n\n... (truncated)"

    url = TELEGRAM_API_URL.format(bot_token)
    data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                logger.info("✅ Telegram notification sent successfully!")
                return True
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        except Exception as e:
            logger.error(f"❌ Request error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    return False


async def scrape_ipo_gmp_data():
    browser = None
    try:
        logger.info("Starting IPO GMP scraper (InvestorGain)...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            page.set_default_timeout(60000)

            logger.info("Navigating to InvestorGain...")
            await page.goto(WEBSITE_URL, wait_until="domcontentloaded", timeout=60000)

            logger.info("Waiting for table to load...")
            try:
                await page.wait_for_selector("table", timeout=30000)
                await page.wait_for_timeout(3000)
            except PlaywrightTimeoutError:
                logger.error("Table not found on page")
                return []

            logger.info("Extracting table data...")
            
            tables = await page.query_selector_all("table")
            target_table = None
            for table in tables:
                headers = await table.query_selector_all("th")
                header_texts = [await h.inner_text() for h in headers]
                if any("gmp" in t.lower() for t in header_texts) and any("price" in t.lower() for t in header_texts):
                    target_table = table
                    break

            if not target_table:
                logger.error("Could not find the GMP table")
                return []

            rows = await target_table.query_selector_all("tr")
            ipos = []
            today = datetime.now()

            for row in rows:
                cells = await row.query_selector_all("td")
                if len(cells) < 10:
                    continue
                
                cell_texts = []
                for cell in cells:
                    text = await cell.inner_text()
                    text = " ".join(text.split())
                    cell_texts.append(text.strip())

                name_raw = cell_texts[0] if len(cell_texts) > 0 else "Unknown"
                gmp_raw = cell_texts[1] if len(cell_texts) > 1 else "₹-- (0.00%)"
                price = cell_texts[4] if len(cell_texts) > 4 else "N/A"
                open_date = cell_texts[7] if len(cell_texts) > 7 else "N/A"
                close_date = cell_texts[8] if len(cell_texts) > 8 else "N/A"

                # Clean up dates (remove extra GMP text like "15-Oct GMP: 500")
                open_date = re.sub(r'\s*GMP:.*', '', open_date)
                close_date = re.sub(r'\s*GMP:.*', '', close_date)

                anchor = cell_texts[-1] if len(cell_texts) > 0 else ""
                if "✅" not in anchor or gmp_raw == "₹-- (0.00%)":
                    continue

                # CLEAN THE NAME: Remove the "@118.00 (2.61%)" part
                name = re.sub(r'@.*$', '', name_raw).strip()
                name = re.sub(r'\s+(IPO|BSE|NSE|SME)?[UOCTC]+$', '', name).strip()

                # Parse GMP percentage
                gmp_percent = 0.0
                match = re.search(r'\((\d+\.?\d*)%\)', gmp_raw)
                if match:
                    gmp_percent = float(match.group(1))
                
                gmp_amount = gmp_raw.split(' ')[0]

                # Parse dates for filtering and sorting
                try:
                    parsed_close = datetime.strptime(close_date + " 2026", "%d-%b %Y")
                except:
                    parsed_close = datetime(2099, 12, 31)

                # FILTER: Only include IPOs that haven't closed yet (or close today)
                if parsed_close.date() < today.date():
                    continue

                ipos.append({
                    "name": name,
                    "gmp": gmp_amount,
                    "gmp_percent": gmp_percent,
                    "price": price,
                    "open": open_date,
                    "close": close_date,
                    "sort_date": parsed_close
                })

            # Sort the IPOs by the closing date
            ipos.sort(key=lambda x: x['sort_date'])
            
            logger.info(f"Found {len(ipos)} active IPOs")
            return ipos[:15]

    except Exception as e:
        logger.error(f"Error occurred during scraping: {e}")
        return []
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


async def main():
    start_time = time.time()
    try:
        logger.info("IPO GMP Scraper Starting...")
        ipos = await scrape_ipo_gmp_data()

        if ipos:
            logger.info(f"Successfully scraped {len(ipos)} IPO records")
            bot_token = os.getenv("BOT_TOKEN")
            chat_id = os.getenv("CHAT_ID")
            if bot_token and chat_id:
                send_telegram_alert(ipos, bot_token, chat_id)
            else:
                logger.warning("⚠️ Telegram credentials not found.")
            sys.exit(0)
        else:
            logger.info("No IPO opportunities found")
            sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info(f"Scraper completed in {time.time() - start_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
