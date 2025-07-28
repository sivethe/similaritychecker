#!/usr/bin/env python3
"""
Master test runner for the Similarity Checker project.

This script runs all test suites for the project components:
- generate_baseline.py tests
- compare_json_similarity_fast.py tests

Usage:
    python3 run_all_tests.py                # Run all tests
    python3 run_all_tests.py --verbose      # Run with detailed output
    python3 run_all_tests.py --baseline     # Run only baseline tests
    python3 run_all_tests.py --similarity   # Run only similarity tests
    python3 run_all_tests.py --update       # Update expected results
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Tuple

class TestSuite:
    def __init__(self, name: str, script_path: str, description: str):
        self.name = name
        self.script_path = script_path
        self.description = description

class MasterTestRunner:
    def __init__(self):
        # Determine the working directory (project root)
        current_dir = Path.cwd()
        if current_dir.name == "tests":
            self.project_root = current_dir.parent
        else:
            self.project_root = current_dir
        
        # Define test suites
        self.test_suites = [
            TestSuite(
                "baseline",
                str(self.project_root / "tests" / "test_generate_baseline.py"),
                "Tests for generate_baseline.py - string extraction and baseline generation"
            ),
            TestSuite(
                "similarity",
                str(self.project_root / "tests" / "test_compare_similarity.py"),
                "Tests for compare_json_similarity_fast.py - substring matching functionality"
            )
        ]
    
    def run_test_suite(self, suite: TestSuite, args: argparse.Namespace) -> Tuple[bool, str]:
        """Run a single test suite and return (success, output)."""
        print(f"\n{'='*60}")
        print(f"🧪 Running {suite.name.upper()} TEST SUITE")
        print(f"📄 {suite.description}")
        print(f"{'='*60}")
        
        # Build command
        cmd = [sys.executable, suite.script_path]
        
        if args.verbose:
            cmd.append("--verbose")
        if args.update:
            cmd.append("--update")
        if args.test:
            cmd.extend(["--test", args.test])
        
        # Add suite-specific arguments
        if suite.name == "similarity" and args.min_words:
            cmd.extend(["--min-words", str(args.min_words)])
        
        try:
            # Run the test suite
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=False,  # Let output show in real-time
                text=True
            )
            
            success = result.returncode == 0
            return success, f"Test suite '{suite.name}' {'passed' if success else 'failed'}"
            
        except Exception as e:
            return False, f"Error running test suite '{suite.name}': {e}"
    
    def run_all_tests(self, args: argparse.Namespace) -> None:
        """Run all or selected test suites."""
        # Filter test suites based on arguments
        suites_to_run = []
        
        if args.baseline and not args.similarity:
            suites_to_run = [s for s in self.test_suites if s.name == "baseline"]
        elif args.similarity and not args.baseline:
            suites_to_run = [s for s in self.test_suites if s.name == "similarity"]
        else:
            # Run all suites
            suites_to_run = self.test_suites
        
        if not suites_to_run:
            print("❌ No test suites selected to run")
            return
        
        print(f"🚀 Running {len(suites_to_run)} test suite(s)")
        if args.update:
            print("📝 Update mode: Will update expected outputs")
        
        # Run each test suite
        results = []
        for suite in suites_to_run:
            success, message = self.run_test_suite(suite, args)
            results.append((suite.name, success, message))
        
        # Print summary
        self.print_summary(results)
        
        # Exit with error code if any tests failed
        if any(not success for _, success, _ in results) and not args.update:
            sys.exit(1)
    
    def print_summary(self, results: List[Tuple[str, bool, str]]) -> None:
        """Print a summary of all test suite results."""
        print(f"\n{'='*60}")
        print(f"📊 MASTER TEST SUMMARY")
        print(f"{'='*60}")
        
        passed_suites = 0
        total_suites = len(results)
        
        for suite_name, success, message in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{status} - {suite_name.upper()}: {message}")
            if success:
                passed_suites += 1
        
        print(f"\n🎯 Overall Result: {passed_suites}/{total_suites} test suites passed")
        
        if passed_suites == total_suites:
            print("🎉 All test suites passed successfully!")
        else:
            print("💥 Some test suites failed - check output above for details")
        
        print(f"{'='*60}")

def main():
    parser = argparse.ArgumentParser(
        description="Master test runner for Similarity Checker project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_all_tests.py                      # Run all test suites
  python3 run_all_tests.py --verbose            # Run with detailed output
  python3 run_all_tests.py --baseline           # Run only baseline tests
  python3 run_all_tests.py --similarity         # Run only similarity tests
  python3 run_all_tests.py --update             # Update expected results
  python3 run_all_tests.py --test sourceSubstring  # Run specific test in all suites
        """
    )
    
    # Test suite selection
    parser.add_argument("--baseline", action="store_true",
                       help="Run only baseline generation tests")
    parser.add_argument("--similarity", action="store_true",
                       help="Run only similarity comparison tests")
    
    # Common test options
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--update", action="store_true",
                       help="Update expected output files instead of testing")
    parser.add_argument("--test", type=str,
                       help="Run specific test (partial name match)")
    
    # Similarity-specific options
    parser.add_argument("--min-words", type=int, default=4,
                       help="Minimum word combination length for similarity tests (default: 4)")
    
    args = parser.parse_args()
    
    try:
        runner = MasterTestRunner()
        runner.run_all_tests(args)
        
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
