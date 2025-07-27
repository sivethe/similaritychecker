#!/usr/bin/env python3
"""
Testing framework for generate_baseline.py

This script runs generate_baseline.py against test files in the testData/ directory
and compares the output to expected results to ensure no regressions.

Usage:
    python3 test_generate_baseline.py              # Run all tests
    python3 test_generate_baseline.py --verbose    # Run with detailed output
    python3 test_generate_baseline.py --update     # Update expected results
    python3 test_generate_baseline.py --test testMultineErrMsg  # Run specific test
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", expected_count: int = 0, actual_count: int = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.expected_count = expected_count
        self.actual_count = actual_count

class BaselineTestFramework:
    def __init__(self, test_dir: str = "testData", baseline_script: str = "generate_baseline.py"):
        # Determine the working directory (project root)
        # If we're in the tests directory, go up one level
        current_dir = Path.cwd()
        if current_dir.name == "tests":
            project_root = current_dir.parent
        else:
            project_root = current_dir
            
        self.test_dir = Path(test_dir)
        # If test_dir is relative, make it relative to project root
        if not self.test_dir.is_absolute():
            self.test_dir = project_root / self.test_dir
            
        self.baseline_script = Path(baseline_script)
        # If baseline_script is relative, make it relative to project root
        if not self.baseline_script.is_absolute():
            self.baseline_script = project_root / self.baseline_script
            
        self.project_root = project_root
        self.test_results: List[TestResult] = []
        
        # Ensure test directory exists
        self.test_dir.mkdir(exist_ok=True)
        
        if not self.baseline_script.exists():
            raise FileNotFoundError(f"Baseline script not found: {self.baseline_script}")
    
    def discover_test_files(self) -> List[Path]:
        """Discover all test files in the test directory."""
        test_files = []
        for ext in ['.c', '.h', '.cpp', '.py', '.js', '.ts', '.java', '.go', '.rb', '.rs']:
            test_files.extend(self.test_dir.glob(f"*{ext}"))
        
        # Filter out expected output files
        test_files = [f for f in test_files if not f.name.endswith('_output.json')]
        return sorted(test_files)
    
    def get_expected_output_file(self, test_file: Path) -> Path:
        """Get the expected output file path for a test file."""
        return self.test_dir / f"{test_file.stem}_output.json"
    
    def run_baseline_script(self, test_file: Path, verbose: bool = False) -> Tuple[bool, str, Optional[List[str]]]:
        """Run generate_baseline.py on a test file and return the result."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            cmd = [sys.executable, str(self.baseline_script), str(test_file), temp_output_path]
            if verbose:
                cmd.append('--verbose')
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                return False, f"Script failed with error: {result.stderr}", None
            
            # Read the generated output
            try:
                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    output_data = json.load(f)
                return True, "", output_data
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON output: {e}", None
            except Exception as e:
                return False, f"Error reading output: {e}", None
        
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_output_path)
            except:
                pass
    
    def load_expected_output(self, expected_file: Path) -> Tuple[bool, str, Optional[List[str]]]:
        """Load the expected output from a file."""
        if not expected_file.exists():
            return False, f"Expected output file not found: {expected_file}", None
        
        try:
            with open(expected_file, 'r', encoding='utf-8') as f:
                expected_data = json.load(f)
            return True, "", expected_data
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in expected file: {e}", None
        except Exception as e:
            return False, f"Error reading expected file: {e}", None
    
    def compare_outputs(self, expected: List[str], actual: List[str], test_name: str) -> TestResult:
        """Compare expected and actual outputs."""
        expected_set = set(expected)
        actual_set = set(actual)
        
        if expected_set == actual_set:
            return TestResult(
                test_name, 
                True, 
                f"✅ PASS: Outputs match ({len(actual)} strings)",
                len(expected),
                len(actual)
            )
        
        # Detailed comparison
        missing_strings = expected_set - actual_set
        extra_strings = actual_set - expected_set
        
        error_details = []
        if missing_strings:
            error_details.append(f"Missing {len(missing_strings)} expected strings:")
            for s in sorted(list(missing_strings)[:3]):  # Show first 3
                error_details.append(f"  - {s[:80]}{'...' if len(s) > 80 else ''}")
            if len(missing_strings) > 3:
                error_details.append(f"  ... and {len(missing_strings) - 3} more")
        
        if extra_strings:
            error_details.append(f"Found {len(extra_strings)} unexpected strings:")
            for s in sorted(list(extra_strings)[:3]):  # Show first 3
                error_details.append(f"  + {s[:80]}{'...' if len(s) > 80 else ''}")
            if len(extra_strings) > 3:
                error_details.append(f"  ... and {len(extra_strings) - 3} more")
        
        return TestResult(
            test_name,
            False,
            f"❌ FAIL: Outputs differ (expected {len(expected)}, got {len(actual)})\n" + "\n".join(error_details),
            len(expected),
            len(actual)
        )
    
    def update_expected_output(self, test_file: Path, output_data: List[str]) -> bool:
        """Update the expected output file for a test."""
        expected_file = self.get_expected_output_file(test_file)
        try:
            with open(expected_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error updating expected output for {test_file.name}: {e}")
            return False
    
    def run_single_test(self, test_file: Path, verbose: bool = False, update_expected: bool = False) -> TestResult:
        """Run a single test case."""
        test_name = test_file.name
        
        if verbose:
            print(f"\n🧪 Running test: {test_name}")
        
        # Run the baseline script
        success, error_msg, actual_output = self.run_baseline_script(test_file, verbose)
        if not success:
            return TestResult(test_name, False, f"❌ FAIL: {error_msg}")
        
        if update_expected:
            # Update mode: save the current output as expected
            if self.update_expected_output(test_file, actual_output):
                return TestResult(test_name, True, f"📝 UPDATED: Expected output saved ({len(actual_output)} strings)")
            else:
                return TestResult(test_name, False, "❌ FAIL: Could not update expected output")
        
        # Test mode: compare with expected output
        expected_file = self.get_expected_output_file(test_file)
        success, error_msg, expected_output = self.load_expected_output(expected_file)
        if not success:
            return TestResult(test_name, False, f"❌ FAIL: {error_msg}")
        
        return self.compare_outputs(expected_output, actual_output, test_name)
    
    def run_all_tests(self, verbose: bool = False, update_expected: bool = False, specific_test: Optional[str] = None) -> None:
        """Run all tests or a specific test."""
        test_files = self.discover_test_files()
        
        if specific_test:
            # Filter to specific test
            test_files = [f for f in test_files if specific_test.lower() in f.stem.lower()]
            if not test_files:
                print(f"❌ No test files found matching: {specific_test}")
                return
        
        if not test_files:
            print("❌ No test files found in test directory")
            return
        
        print(f"🔍 Found {len(test_files)} test file(s)")
        if update_expected:
            print("📝 Update mode: Will update expected outputs")
        
        for test_file in test_files:
            result = self.run_single_test(test_file, verbose, update_expected)
            self.test_results.append(result)
            
            if not verbose:
                # Show concise output
                status = "✅" if result.passed else "❌"
                print(f"{status} {result.name} ({result.actual_count} strings)")
            else:
                print(f"\n{result.message}")
    
    def print_summary(self) -> None:
        """Print a summary of all test results."""
        if not self.test_results:
            return
        
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        
        print(f"\n{'='*60}")
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print(f"\n❌ Failed tests:")
            for result in self.test_results:
                if not result.passed:
                    print(f"  • {result.name}")
        
        print(f"{'='*60}")
    
    def has_failures(self) -> bool:
        """Check if any tests failed."""
        return any(not r.passed for r in self.test_results)

def main():
    parser = argparse.ArgumentParser(
        description="Test framework for generate_baseline.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 test_generate_baseline.py                    # Run all tests
  python3 test_generate_baseline.py --verbose          # Run with detailed output
  python3 test_generate_baseline.py --update           # Update expected results
  python3 test_generate_baseline.py --test testMulti   # Run specific test
        """
    )
    
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--update", action="store_true",
                       help="Update expected output files instead of testing")
    parser.add_argument("--test", type=str,
                       help="Run specific test (partial name match)")
    parser.add_argument("--test-dir", default="testData",
                       help="Directory containing test files (default: testData)")
    parser.add_argument("--script", default="generate_baseline.py",
                       help="Path to generate_baseline.py script (default: generate_baseline.py)")
    
    args = parser.parse_args()
    
    try:
        framework = BaselineTestFramework(args.test_dir, args.script)
        framework.run_all_tests(args.verbose, args.update, args.test)
        framework.print_summary()
        
        # Exit with error code if tests failed
        if framework.has_failures() and not args.update:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
