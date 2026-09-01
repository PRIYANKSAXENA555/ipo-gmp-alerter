#!/usr/bin/env python3
"""
IPO GMP Scraper - Robust Production Version
==========================================

A robust, production-ready scraper for IPO Grey Market Premium data.
Optimized for reliability and performance.
"""

import asyncio
import pandas as pd
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
import json
import logging
import sys
from datetime import datetime, timedelta
import re
import requests
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ipo_scraper.log"),
    ],
)
logger = logging.getLogger(__name__)

# Constants
MIN_GAIN_PERCENTAGE = 20.0
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
TELEGRAM_API_URL = "https://api.telegram.org/bot{}/sendMessage"
WEBSITE_URL = "https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/"


def parse_date_range(date_str: str) -> Optional[datetime]:
    """Parse date range string like '3-7 Oct' and return the end date."""
    if not date_str or date_str.strip() in ("TBA", "-", ""):
        return None

    try:
        date_match = re.search(r"(\d+)-(\d+)\s+(\w+)", date_str.strip())
        if not date_match:
            return None

        end_day = int(date_match.group(2))
        month_str = date_match.group(3)

        month_map = {
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12,
        }

        month = month_map.get(month_str)
        if not month:
            return None

        current_year = datetime.now().year
        end_date = datetime(current_year, month, end_day)
        return end_date

    except Exception:
        return None


def parse_gain_percentage(gain_str: str) -> float:
    """Parse gain percentage from string like '26.31%'."""
    if not gain_str or gain_str.strip() in ("-", "-%", ""):
        return 0.0

    try:
        gain_match = re.search(r"(\d+\.?\d*)%", gain_str.strip())
        if gain_match:
            return float(gain_match.group(1))
    except Exception:
        pass

    return 0.0


def filter_open_mainboard_ipos(df: pd.DataFrame) -> pd.DataFrame:
    """Filter for Mainboard IPOs with >=5% gains that are currently open."""
    if df.empty:
        return df

    # Filter for Mainboard IPOs only
    # Note: Using a safer lookup in case 'Type' is not exactly named 'Type'
    type_col = None
    for col in df.columns:
        if 'type' in col.lower():
            type_col = col
            break
            
    if type_col:
        mainboard_df = df[df[type_col] == "Mainboard"].copy()
    else:
        logger.warning("Could not find 'Type' column. Assuming all are Mainboard.")
        mainboard_df = df.copy()

    if mainboard_df.empty:
        return mainboard_df

    today = datetime.now().date()
    open_ipos = []

    for idx, row in mainboard_df.iterrows():
        try:
            # Safer column lookup
            date_str = ""
            gain_str = ""
            if "Date" in row:
                date_str = row["Date"]
            if "Gain" in row:
                gain_str = row["Gain"]

            gain_percentage = parse_gain_percentage(gain_str)
            end_date = parse_date_range(date_str)
            is_open = (end_date and end_date.date() >= today) or not end_date
            has_good_gain = gain_percentage >= MIN_GAIN_PERCENTAGE

            if is_open and has_good_gain:
                open_ipos.append(row)
        except Exception:
            continue

    if open_ipos:
        filtered_df = pd.DataFrame(open_ipos)
        filtered_df["Gain_Numeric"] = filtered_df["Gain"].apply(parse_gain_percentage)
        filtered_df = filtered_df.sort_values("Gain_Numeric", ascending=False)
        filtered_df = filtered_df.drop("Gain_Numeric", axis=1)
        logger.info(
            f"Found {len(filtered_df)} currently open Mainboard IPOs with >=5% gains"
        )
    else:
        logger.info("No currently open Mainboard IPOs with >=5% gains found")
        filtered_df = pd.DataFrame()

    return filtered_df


def send_telegram_alert(df: pd.DataFrame, bot_token: str, chat_id: str) -> bool:
    """Send IPO data to Telegram group."""
    if not bot_token or not chat_id:
        return False

    # Get current date
    from datetime import datetime

    current_date = datetime.now().strftime("%B %d, %Y")

    if df.empty:
        message = f"📊 No IPO opportunities found today ({current_date})."
    else:
        message = f"🚀 <b>Daily IPO Opportunities Found!</b>\n📅 {current_date}\n\n"
        for idx, row in df.iterrows():
            # Safe access for potential column name variations
            stock_name = row.get('Stock / IPO', row.get('Stock', 'Unknown'))
            gmp = row.get('IPO GMP', row.get('GMP', 'N/A'))
            price = row.get('IPO Price', row.get('Price', 'N/A'))
            gain = row.get('Gain', 'N/A')
            date = row.get('Date', 'N/A')

            message += f"📈 <b>{stock_name}</b>\n"
            message += f"💰 GMP: {gmp}\n"
            message += f"💵 Price: {price}\n"
            message += f"📊 Gain: {gain}\n"
            message += f"📅 Date: {date}\n\n"

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
                logger.error(
                    f"❌ Telegram API error (attempt {attempt + 1}): {response.text}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        except Exception as e:
            logger.error(f"❌ Telegram request error (attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

    return False


async def scrape_ipo_gmp_data() -> Optional[pd.DataFrame]:
    """Scrape IPO GMP data from the website."""
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

            # Wait for table
            try:
                await page.wait_for_selector("table", timeout=10000)
            except PlaywrightTimeoutError:
                logger.error("Table not found on page")
                return None

            logger.info("Extracting table data...")

            # Extract table data
            table_data = await page.evaluate(
                """
                () => {
                    const table = document.querySelector('table');
                    if (!table) return null;
                    
                    const rows = table.querySelectorAll('tr');
                    const data = [];
                    
                    for (let i = 0; i < rows.length; i++) {
                        const row = rows[i];
                        const cells = row.querySelectorAll('td, th');
                        const rowData = [];
                        
                        for (let j = 0; j < cells.length; j++) {
                            const cell = cells[j];
                            let text = cell.textContent.trim();
                            
                            const link = cell.querySelector('a');
                            if (link) {
                                text = link.textContent.trim();
                            }
                            
                            rowData.push(text);
                        }
                        
                        if (rowData.length > 0) {
                            data.push(rowData);
                        }
                    }
                    
                    return data;
                }
                """
            )

            if not table_data or len(table_data) <= 1:
                logger.error("No table data extracted")
                return None

            logger.info(f"Found table with {len(table_data)} rows")

            # Convert to DataFrame
            headers = table_data[0]
            rows = table_data[1:]
            
            # CLEAN THE HEADERS: Strip whitespace, remove empty strings, and rename duplicates
            clean_headers = []
            seen_headers = {}
            for i, h in enumerate(headers):
                h = h.strip()  # Remove spaces
                if not h:  # If header is empty, give it a default name
                    h = f"Column_{i}"
                # Handle duplicate columns (e.g., if there are two "Type")
                if h in seen_headers:
                    seen_headers[h] += 1
                    h = f"{h}_{seen_headers[h]}"
                else:
                    seen_headers[h] = 0
                clean_headers.append(h)

            df = pd.DataFrame(rows, columns=clean_headers)

            # Filter for open Mainboard IPOs
            filtered_df = filter_open_mainboard_ipos(df)

            if not filtered_df.empty:
                logger.info("\n" + "=" * 80)
                logger.info("CURRENTLY OPEN MAINBOARD IPOs WITH >=5% GAINS")
                logger.info("=" * 80)
                logger.info(filtered_df.to_string(index=False))

            return filtered_df

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
    """Main function to run the scraper."""
    start_time = time.time()

    try:
        logger.info("IPO GMP Scraper Starting...")
        logger.info("=" * 50)

        df = await scrape_ipo_gmp_data()

        if df is not None and not df.empty:
            logger.info(f"Successfully scraped {len(df)} IPO records")

            # Save data
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_file = f"ipo_gmp_data_{timestamp}.csv"
                json_file = f"ipo_gmp_data_{timestamp}.json"

                df.to_csv(csv_file, index=False)
                df.to_json(json_file, orient="records", indent=2)

                logger.info(f"Data saved to: {csv_file}")
                logger.info(f"Data also saved to: {json_file}")
            except Exception as e:
                logger.error(f"Error saving data: {e}")

            # Send Telegram notification
            bot_token = os.getenv("BOT_TOKEN")
            chat_id = os.getenv("CHAT_ID")

            if bot_token and chat_id:
                success = send_telegram_alert(df, bot_token, chat_id)
                if not success:
                    logger.error("Failed to send Telegram notification")
            else:
                logger.warning(
                    "⚠️ Telegram credentials not found. Set BOT_TOKEN and CHAT_ID environment variables."
                )

            sys.exit(0)
        else:
            logger.info("No IPO opportunities found or scraping failed")
            sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sys.exit(1)
    finally:
        elapsed_time = time.time() - start_time
        logger.info(f"Scraper completed in {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
