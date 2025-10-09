#!/usr/bin/env python3
"""
Test Runner for IPO GMP Scraper
===============================

Convenient script to run all tests with proper configuration.
Supports different test modes and coverage reporting.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_type="all", coverage=True, verbose=True):
    """
    Run tests with specified configuration.
    
    Args:
        test_type: Type of tests to run ('all', 'unit', 'integration')
        coverage: Whether to generate coverage reports
        verbose: Whether to run in verbose mode
    """
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=ipo_gmp_scraper", "--cov-report=html", "--cov-report=xml"])
    
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    
    cmd.append("tests/")
    
    print(f"🧪 Running {test_type} tests...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("✅ All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed with exit code {e.returncode}")
        return False


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Run IPO GMP Scraper tests")
    parser.add_argument(
        "--type", 
        choices=["all", "unit", "integration"], 
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--no-coverage", 
        action="store_true",
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "--quiet", 
        action="store_true",
        help="Run in quiet mode"
    )
    
    args = parser.parse_args()
    
    success = run_tests(
        test_type=args.type,
        coverage=not args.no_coverage,
        verbose=not args.quiet
    )
    
    if success:
        print("\n🎉 Test run completed successfully!")
        if not args.no_coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n💥 Test run failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
