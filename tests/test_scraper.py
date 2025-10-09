#!/usr/bin/env python3
"""
Unit tests for IPO GMP Scraper
==============================

Comprehensive test suite for the IPO GMP scraper functionality.
Tests data parsing, filtering, and validation logic.
"""

import unittest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipo_gmp_scraper import (
    parse_date_range,
    parse_gain_percentage,
    filter_open_mainboard_ipos
)


class TestDateParsing(unittest.TestCase):
    """Test date range parsing functionality."""
    
    def test_valid_date_range(self):
        """Test parsing valid date ranges."""
        # Test with current year
        result = parse_date_range("3-7 Oct")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 7)
    
    def test_invalid_date_formats(self):
        """Test handling of invalid date formats."""
        self.assertIsNone(parse_date_range("TBA"))
        self.assertIsNone(parse_date_range("-"))
        self.assertIsNone(parse_date_range(""))
        self.assertIsNone(parse_date_range("Invalid"))
    
    def test_edge_cases(self):
        """Test edge cases in date parsing."""
        # Single day range
        result = parse_date_range("15-15 Oct")
        self.assertIsNotNone(result)
        self.assertEqual(result.day, 15)
        
        # Different months
        result = parse_date_range("25-30 Dec")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 12)
        self.assertEqual(result.day, 30)


class TestGainParsing(unittest.TestCase):
    """Test gain percentage parsing functionality."""
    
    def test_valid_gain_percentages(self):
        """Test parsing valid gain percentages."""
        self.assertEqual(parse_gain_percentage("26.31%"), 26.31)
        self.assertEqual(parse_gain_percentage("5.0%"), 5.0)
        self.assertEqual(parse_gain_percentage("100%"), 100.0)
        self.assertEqual(parse_gain_percentage("0.5%"), 0.5)
    
    def test_invalid_gain_formats(self):
        """Test handling of invalid gain formats."""
        self.assertEqual(parse_gain_percentage("-"), 0.0)
        self.assertEqual(parse_gain_percentage("-%"), 0.0)
        self.assertEqual(parse_gain_percentage(""), 0.0)
        self.assertEqual(parse_gain_percentage("Invalid"), 0.0)
        self.assertEqual(parse_gain_percentage("No percentage"), 0.0)
    
    def test_edge_cases(self):
        """Test edge cases in gain parsing."""
        # Zero gain
        self.assertEqual(parse_gain_percentage("0%"), 0.0)
        
        # Very high gain
        self.assertEqual(parse_gain_percentage("999.99%"), 999.99)
        
        # Decimal precision
        self.assertEqual(parse_gain_percentage("5.123%"), 5.123)


class TestIPOFiltering(unittest.TestCase):
    """Test IPO filtering functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Use future dates to ensure IPOs are considered "open"
        from datetime import datetime, timedelta
        future_date = datetime.now() + timedelta(days=30)
        future_month = future_date.strftime('%b')
        future_day = future_date.day
        
        self.sample_data = pd.DataFrame([
            {
                'Stock / IPO': 'Test IPO 1',
                'IPO GMP': '₹50',
                'IPO Price': '₹100',
                'Gain': '50%',
                'Date': f'{future_day}-{future_day+3} {future_month}',
                'Type': 'Mainboard'
            },
            {
                'Stock / IPO': 'Test IPO 2',
                'IPO GMP': '₹5',
                'IPO Price': '₹100',
                'Gain': '5%',
                'Date': f'{future_day+5}-{future_day+10} {future_month}',
                'Type': 'Mainboard'
            },
            {
                'Stock / IPO': 'Test IPO 3',
                'IPO GMP': '₹2',
                'IPO Price': '₹100',
                'Gain': '2%',
                'Date': f'{future_day+15}-{future_day+20} {future_month}',
                'Type': 'Mainboard'
            },
            {
                'Stock / IPO': 'Test SME IPO',
                'IPO GMP': '₹20',
                'IPO Price': '₹100',
                'Gain': '20%',
                'Date': f'{future_day+25}-{future_day+30} {future_month}',
                'Type': 'SME'
            }
        ])
    
    def test_filter_mainboard_only(self):
        """Test filtering for Mainboard IPOs only."""
        result = filter_open_mainboard_ipos(self.sample_data)
        
        # Should exclude SME IPO and low gain IPO (2% < 5% threshold)
        self.assertEqual(len(result), 2)  # Only 50% and 5% gain IPOs
        self.assertTrue(all(result['Type'] == 'Mainboard'))
    
    def test_filter_by_gain_threshold(self):
        """Test filtering by minimum gain threshold."""
        result = filter_open_mainboard_ipos(self.sample_data)
        
        # Should exclude IPO with 2% gain (below 5% threshold)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(result['Gain'].str.contains('%')))
    
    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        empty_df = pd.DataFrame()
        result = filter_open_mainboard_ipos(empty_df)
        self.assertTrue(result.empty)
    
    def test_no_mainboard_ipos(self):
        """Test handling when no Mainboard IPOs exist."""
        sme_only_data = self.sample_data[self.sample_data['Type'] == 'SME']
        result = filter_open_mainboard_ipos(sme_only_data)
        self.assertTrue(result.empty)
    
    def test_sorting_by_gain(self):
        """Test that results are sorted by gain percentage."""
        result = filter_open_mainboard_ipos(self.sample_data)
        
        if not result.empty:
            # Should be sorted by gain (highest first)
            gains = [parse_gain_percentage(gain) for gain in result['Gain']]
            self.assertEqual(gains, sorted(gains, reverse=True))


class TestDataValidation(unittest.TestCase):
    """Test data validation functionality."""
    
    def test_dataframe_structure(self):
        """Test that filtered DataFrame has correct structure."""
        from datetime import datetime, timedelta
        future_date = datetime.now() + timedelta(days=30)
        future_month = future_date.strftime('%b')
        future_day = future_date.day
        
        sample_data = pd.DataFrame([
            {
                'Stock / IPO': 'Test IPO',
                'IPO GMP': '₹50',
                'IPO Price': '₹100',
                'Gain': '50%',
                'Date': f'{future_day}-{future_day+3} {future_month}',
                'Type': 'Mainboard'
            }
        ])
        
        result = filter_open_mainboard_ipos(sample_data)
        
        # Should have all required columns
        required_columns = ['Stock / IPO', 'IPO GMP', 'IPO Price', 'Gain', 'Date', 'Type']
        for col in required_columns:
            self.assertIn(col, result.columns)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete workflow."""
    
    @patch('ipo_gmp_scraper.logger')
    def test_complete_filtering_workflow(self, mock_logger):
        """Test the complete filtering workflow."""
        from datetime import datetime, timedelta
        future_date = datetime.now() + timedelta(days=30)
        future_month = future_date.strftime('%b')
        future_day = future_date.day
        
        # Create comprehensive test data
        test_data = pd.DataFrame([
            {
                'Stock / IPO': 'High Gain IPO',
                'IPO GMP': '₹100',
                'IPO Price': '₹100',
                'Gain': '100%',
                'Date': f'{future_day}-{future_day+3} {future_month}',
                'Type': 'Mainboard'
            },
            {
                'Stock / IPO': 'Low Gain IPO',
                'IPO GMP': '₹3',
                'IPO Price': '₹100',
                'Gain': '3%',
                'Date': f'{future_day+5}-{future_day+10} {future_month}',
                'Type': 'Mainboard'
            },
            {
                'Stock / IPO': 'SME IPO',
                'IPO GMP': '₹50',
                'IPO Price': '₹100',
                'Gain': '50%',
                'Date': f'{future_day+15}-{future_day+20} {future_month}',
                'Type': 'SME'
            }
        ])
        
        result = filter_open_mainboard_ipos(test_data)
        
        # Should only include high gain Mainboard IPO
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['Stock / IPO'], 'High Gain IPO')
        self.assertEqual(result.iloc[0]['Gain'], '100%')


if __name__ == '__main__':
    # Configure test runner
    unittest.main(verbosity=2)