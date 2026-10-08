#!/usr/bin/env python3
"""
IPO GMP Scraper - Robust Production Version
==========================================
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


def parse_gain_percentage(gain_str: str) -> float:
    if not gain_str or gain_str.strip() in ("-", "-%", ""):
        return 0.0
    try:
        match = re.search(r"(\d+\.?\d*)%", gain_str.strip())
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return 0.0


def send_telegram_alert(df: pd.DataFrame, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        return False

    current_date = datetime.now().strftime("%B %d, %Y")

    if df.empty:
        message = f"📊 No IPO opportunities found today ({current_date})."
    else:
        message = f"🚀 <b>Daily IPO Opportunities Found!</b>\n📅 {current_date}\n\n"
        for idx, row in df.iterrows():
            stock_name = row.get('IPO Name', 'Unknown')
            gmp = row.get('IPO GMP', 'N/A')
            price = row.get('Price Band', 'N/A')
            trend = row.get('Trend', 'N/A')
            date = row.get('Date', 'N/A')
            status = row.get('Status', 'N/A')

            message += f"📈 <b>{stock_name}</b>\n"
            message += f"💰 GMP: {gmp}\n"
            message += f"💵 Price Band: {price}\n"
            message += f"📊 Trend: {trend}\n"
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

            try:
                await page.wait_for_selector("table", timeout=10000)
            except PlaywrightTimeoutError:
                logger.error("Table not found on page")
                return None

            logger.info("Extracting table data...")

            # Get the table that contains "IPO Name"
            tables = await page.query_selector_all("table")
            target_table = None
            for table in tables:
                headers = await table.query_selector_all("th")
                for th in headers:
                    text = await th.inner_text()
                    if "ipo name" in text.lower():
                        target_table = table
                        break
                if target_table:
                    break

            if not target_table:
                logger.error("Could not find the correct table")
                return None

            # Extract data from the target table
            rows = await target_table.query_selector_all("tr")
            data = []
            for row in rows:
                cells = await row.query_selector_all("td, th")
                row_data = []
                for cell in cells:
                    # Get all inner text, including hidden spans
                    text = await cell.inner_text()
                    
                    # Try to extract the GMP value specifically (look for ₹ or numbers)
                    # If the text is just a color, try to get the full HTML
                    if text.strip() in ['🟢', '🟡', '🔴', '']:
                        html = await cell.inner_html()
                        # Search for numbers in the HTML
                        match = re.search(r'(\d+\.?\d*)', html)
                        if match:
                            text = "₹" + match.group(1)
                    
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

            # Filter
            if "Status" in df.columns:
                df = df[~df["Status"].str.contains('Listed|Closed', case=False, na=False)]

            if not df.empty:
                logger.info("\n" + "=" * 80)
                logger.info("CURRENTLY OPEN IPOs")
                logger.info("=" * 80)
                logger.info(df.to_string(index=False))

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
