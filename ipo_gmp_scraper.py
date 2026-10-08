#!/usr/bin/env python3
"""
IPO GMP Scraper - Final Version Mapped to Screenshot
"""

import asyncio
import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import logging
import sys
import re
import requests
import os
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

MIN_GAIN_PERCENTAGE = 0.0
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
TELEGRAM_API_URL = "https://api.telegram.org/bot{}/sendMessage"
WEBSITE_URL = "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/"


def send_telegram_alert(df: pd.DataFrame, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        return False

    current_date = datetime.now().strftime("%B %d, %Y")

    if df.empty:
        message = f"📊 No IPO opportunities found today ({current_date})."
    else:
        message = f"🚀 <b>Daily IPO Opportunities Found!</b>\n📅 {current_date}\n\n"
        for idx, row in df.iterrows():
            # Use exact column names from the screenshot
            company = row.get('Company', 'Unknown')
            # Split the company name and status (e.g., "Jio Platforms\nUpcoming")
            if isinstance(company, str) and '\n' in company:
                parts = company.split('\n')
                company = parts[0].strip()
                status = parts[1].strip() if len(parts) > 1 else 'N/A'
            else:
                status = 'N/A'

            gmp = row.get('GMP*', row.get('GMP', 'N/A'))
            trend = row.get('Trend', 'N/A')
            price = row.get('Price Band', 'N/A')
            est_gain = row.get('Est. Gain', 'N/A')
            date = row.get('Date', 'N/A')

            message += f"📈 <b>{company}</b>\n"
            message += f"💰 GMP: {gmp}\n"
            message += f"💵 Price Band: {price}\n"
            message += f"📊 Trend: {trend}\n"
            message += f"📈 Est. Gain: {est_gain}\n"
            message += f"📅 Date: {date}\n"
            message += f"📌 Status: {status}\n\n"

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
                logger.error(f"❌ Telegram error (attempt {attempt + 1}): {response.text}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        except Exception as e:
            logger.error(f"❌ Telegram request error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    return False


async def scrape_ipo_gmp_data():
    browser = None
    try:
        logger.info("Starting IPO GMP scraper...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            page.set_default_timeout(20000)

            logger.info("Navigating to IPO GMP page...")
            await page.goto(WEBSITE_URL, wait_until="domcontentloaded")

            # Wait for any table to appear
            try:
                await page.wait_for_selector("table", timeout=10000)
            except PlaywrightTimeoutError:
                logger.error("Table not found on page")
                return None

            logger.info("Extracting table data...")
            
            # Find the table containing "Company" and "GMP*"
            tables = await page.query_selector_all("table")
            target_table = None
            for table in tables:
                headers = await table.query_selector_all("th")
                header_texts = [await h.inner_text() for h in headers]
                if any("company" in t.lower() for t in header_texts) and any("gmp" in t.lower() for t in header_texts):
                    target_table = table
                    break

            if not target_table:
                logger.error("Could not find the correct table with Company and GMP headers")
                return None

            # Extract all rows
            rows = await target_table.query_selector_all("tr")
            data = []
            for row in rows:
                cells = await row.query_selector_all("td, th")
                row_data = []
                for cell in cells:
                    # Get the full inner text. Because some cells have multiple lines (like Company + Status),
                    # we keep the newlines and handle them later.
                    text = await cell.inner_text()
                    row_data.append(text.strip())
                if row_data:
                    data.append(row_data)

            if not data or len(data) <= 1:
                logger.error("No table data extracted")
                return None

            logger.info(f"Found table with {len(data)} rows")
            headers = data[0]
            rows = data[1:]
            df = pd.DataFrame(rows, columns=headers)
            
            logger.info(f"DEBUG - COLUMNS: {list(df.columns)}")
            if not df.empty:
                logger.info(f"DEBUG - FIRST ROW: {df.iloc[0].to_dict()}")

            # Filter out "Listed" or "Closed" if status is in the Company column
            if 'Company' in df.columns:
                df = df[~df['Company'].str.contains('Listed|Closed', case=False, na=False)]

            return df

    except Exception as e:
        logger.error(f"Error occurred during scraping: {e}")
        return None
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
        df = await scrape_ipo_gmp_data()

        if df is not None and not df.empty:
            logger.info(f"Successfully scraped {len(df)} IPO records")
            bot_token = os.getenv("BOT_TOKEN")
            chat_id = os.getenv("CHAT_ID")
            if bot_token and chat_id:
                send_telegram_alert(df, bot_token, chat_id)
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
