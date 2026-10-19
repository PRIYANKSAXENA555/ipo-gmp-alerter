#!/usr/bin/env python3
"""
IPO GMP Scraper - InvestorGain Version
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Telegram Settings
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
TELEGRAM_API_URL = "https://api.telegram.org/bot{}/sendMessage"

# New Website URL
WEBSITE_URL = "https://www.investorgain.com/report/ipo-gmp-live/331/"


def send_telegram_alert(df: pd.DataFrame, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        return False

    current_date = datetime.now().strftime("%B %d, %Y")

    if df.empty:
        message = f"📊 No IPO opportunities found today ({current_date})."
    else:
        message = f"🚀 <b>Daily IPO GMP (InvestorGain)</b>\n📅 {current_date}\n\n"
        for idx, row in df.iterrows():
            name = row.get('Name', 'Unknown')
            gmp = row.get('GMP', 'N/A')
            price = row.get('Price (₹)', 'N/A')
            open_date = row.get('Open', 'N/A')
            close_date = row.get('Close', 'N/A')

            message += f"📈 <b>{name}</b>\n"
            message += f"💰 GMP: {gmp}\n"
            message += f"💵 Price: {price}\n"
            message += f"📅 Open: {open_date} | Close: {close_date}\n\n"

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

            # Wait for the specific table to load
            logger.info("Waiting for table to load...")
            try:
                # Wait for any table that has "GMP" and "Price" headers
                await page.wait_for_selector("table", timeout=30000)
                await page.wait_for_timeout(3000) # Give it a few extra seconds to render
            except PlaywrightTimeoutError:
                logger.error("Table not found on page")
                return None

            logger.info("Extracting table data...")
            
            # Find the correct table
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
                return None

            # Extract rows
            rows = await target_table.query_selector_all("tr")
            data = []
            for row in rows:
                cells = await row.query_selector_all("td, th")
                row_data = []
                for cell in cells:
                    text = await cell.inner_text()
                    # Clean up newlines inside the cell
                    text = " ".join(text.split())
                    row_data.append(text.strip())
                if row_data:
                    data.append(row_data)

            if not data or len(data) <= 1:
                logger.error("No data extracted")
                return None

            # Clean headers (often there are duplicate headers like "Name" due to nested tables)
            headers = data[0]
            clean_headers = []
            for i, h in enumerate(headers):
                # If a header is just "Name" or "GMP", add index to differentiate
                if h in clean_headers:
                    clean_headers.append(f"{h}_{i}")
                else:
                    clean_headers.append(h)

            # Create DataFrame
            df = pd.DataFrame(data[1:], columns=clean_headers)
            
            # Log the columns so we can see what we have
            logger.info(f"DEBUG - COLUMNS: {list(df.columns)}")
            if not df.empty:
                logger.info(f"DEBUG - FIRST ROW: {df.iloc[0].to_dict()}")

            # Filter out "Listed" or "Closed" (usually these are at the bottom)
            # In InvestorGain, the "Anchor" column has ❌ for closed IPOs, so we can filter on that.
            if 'Anchor' in df.columns:
                df = df[df['Anchor'].str.contains('✅', na=False)]
            
            # We only want the current/upcoming IPOs (usually the first 10-15 rows)
            # We can grab the first 15 rows to keep the message concise
            df = df.head(15)

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
