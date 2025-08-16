#!/usr/bin/env python3
"""
Test suite for extract_strings_from_cplusplus.py

This test suite automatically discovers C/C++ test files in testData/cplusplus/,
runs extract_strings_from_cplusplus.py on them, and compares the output against
expected results in corresponding *_output.json files.
"""

import argparse
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import List, Dict, Any, Tuple


class TestExtractStringsFromCplusplus(unittest.TestCase):
    """Test cases for extract_strings_from_cplusplus.py"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class - find the extractor script and test data directory."""
        cls.script_dir = Path(__file__).parent.parent
        cls.extractor_script = cls.script_dir / "extract_strings_from_cplusplus.py"
        cls.test_data_dir = cls.script_dir / "testData" / "cplusplus"
        cls.verbose = False
        
        # Verify extractor script exists
        if not cls.extractor_script.exists():
            raise FileNotFoundError(f"Extractor script not found: {cls.extractor_script}")
        
        # Verify test data directory exists
        if not cls.test_data_dir.exists():
            raise FileNotFoundError(f"Test data directory not found: {cls.test_data_dir}")
    
    @classmethod
    def set_verbose(cls, verbose: bool):
        """Set verbose mode for detailed output comparison."""
        cls.verbose = verbose
    
    def discover_test_files(self) -> List[Tuple[Path, Path]]:
        """
        Discover test files and their expected output files.
        
        Returns:
            List of tuples (test_file_path, expected_output_path)
        """
        test_files = []
        
        # Find all .c and .h files in the test directory
        for pattern in ['*.c', '*.h']:
            for test_file in self.test_data_dir.glob(pattern):
                # Look for corresponding _output.json file
                output_file_name = test_file.stem + "_output.json"
                output_file = self.test_data_dir / output_file_name
                
                if output_file.exists():
                    test_files.append((test_file, output_file))
                else:
                    print(f"Warning: No expected output file found for {test_file.name}")
                    print(f"Expected: {output_file}")
        
        return test_files
    
    def run_extractor(self, input_file: Path) -> Tuple[bool, List[str], str]:
        """
        Run extract_strings_from_cplusplus.py on a test file.
        
        Args:
            input_file: Path to the input C/C++ file
            
        Returns:
            Tuple of (success, extracted_strings, error_message)
        """
        try:
            cmd = [sys.executable, str(self.extractor_script), str(input_file)]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=self.script_dir
            )
            
            if result.returncode != 0:
                return False, [], f"Extractor failed with exit code {result.returncode}: {result.stderr}"
            
            # Parse JSON output
            try:
                extracted_strings = json.loads(result.stdout)
                if not isinstance(extracted_strings, list):
                    return False, [], f"Expected list output, got {type(extracted_strings)}"
                return True, extracted_strings, ""
            except json.JSONDecodeError as e:
                return False, [], f"Failed to parse JSON output: {e}\nOutput was: {result.stdout}"
                
        except Exception as e:
            return False, [], f"Failed to run extractor: {e}"
    
    def load_expected_output(self, output_file: Path) -> Tuple[bool, List[str], str]:
        """
        Load expected output from JSON file.
        
        Args:
            output_file: Path to the expected output JSON file
            
        Returns:
            Tuple of (success, expected_strings, error_message)
        """
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                expected = json.load(f)
                
            if not isinstance(expected, list):
                return False, [], f"Expected list in output file, got {type(expected)}"
                
            return True, expected, ""
            
        except json.JSONDecodeError as e:
            return False, [], f"Failed to parse expected output JSON: {e}"
        except Exception as e:
            return False, [], f"Failed to load expected output: {e}"
    
    def compare_outputs(self, actual: List[str], expected: List[str], test_name: str) -> bool:
        """
        Compare actual and expected outputs.
        
        Args:
            actual: Actual extracted strings
            expected: Expected extracted strings
            test_name: Name of the test for error reporting
            
        Returns:
            True if outputs match, False otherwise
        """
        # Sort both lists for comparison (order shouldn't matter for string extraction)
        actual_sorted = sorted(actual)
        expected_sorted = sorted(expected)
        
        if actual_sorted == expected_sorted:
            return True
        
        # Output detailed comparison if verbose or if test fails
        if self.verbose or actual_sorted != expected_sorted:
            print(f"\n{'='*60}")
            print(f"MISMATCH in {test_name}")
            print(f"{'='*60}")
            print(f"Expected ({len(expected)} strings):")
            for i, s in enumerate(expected_sorted, 1):
                print(f"  {i}. {repr(s)}")
            
            print(f"\nActual ({len(actual)} strings):")
            for i, s in enumerate(actual_sorted, 1):
                print(f"  {i}. {repr(s)}")
            
            # Show differences
            expected_set = set(expected_sorted)
            actual_set = set(actual_sorted)
            
            missing = expected_set - actual_set
            extra = actual_set - expected_set
            
            if missing:
                print(f"\nMissing strings ({len(missing)}):")
                for s in sorted(missing):
                    print(f"  - {repr(s)}")
            
            if extra:
                print(f"\nExtra strings ({len(extra)}):")
                for s in sorted(extra):
                    print(f"  + {repr(s)}")
            
            print(f"{'='*60}\n")
        
        return False
    
    def test_all_files(self):
        """Test all discovered files."""
        test_files = self.discover_test_files()
        
        if not test_files:
            self.skipTest("No test files found in testData/cplusplus/")
        
        print(f"\nRunning tests on {len(test_files)} file(s)...")
        
        failed_tests = []
        passed_tests = []
        
        for test_file, output_file in test_files:
            test_name = test_file.name
            print(f"\nTesting: {test_name}")
            
            # Load expected output
            success, expected, error = self.load_expected_output(output_file)
            if not success:
                failed_tests.append((test_name, f"Failed to load expected output: {error}"))
                continue
            
            # Run extractor
            success, actual, error = self.run_extractor(test_file)
            if not success:
                failed_tests.append((test_name, f"Extractor failed: {error}"))
                continue
            
            # Compare outputs
            if self.compare_outputs(actual, expected, test_name):
                print(f"  ✅ PASS - {len(actual)} strings extracted correctly")
                passed_tests.append(test_name)
            else:
                failed_tests.append((test_name, "Output mismatch"))
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {len(test_files)}")
        print(f"Passed: {len(passed_tests)}")
        print(f"Failed: {len(failed_tests)}")
        
        if passed_tests:
            print(f"\nPassed tests:")
            for test_name in passed_tests:
                print(f"  ✅ {test_name}")
        
        if failed_tests:
            print(f"\nFailed tests:")
            for test_name, reason in failed_tests:
                print(f"  ❌ {test_name}: {reason}")
        
        # Fail the test if any files failed
        if failed_tests:
            self.fail(f"{len(failed_tests)} test file(s) failed")


def main():
    """Main function for running tests from command line."""
    parser = argparse.ArgumentParser(
        description='Test extract_strings_from_cplusplus.py against test files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_extract_strings_from_cplusplus.py                    # Run all tests
  python test_extract_strings_from_cplusplus.py -v                 # Run with verbose output
  python test_extract_strings_from_cplusplus.py --unittest         # Run as unittest

Test Files:
  This script looks for .c and .h files in testData/cplusplus/ and their
  corresponding *_output.json files containing expected extraction results.
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output showing detailed comparisons')
    parser.add_argument('--unittest', action='store_true',
                       help='Run using unittest framework (default: custom runner)')
    
    args = parser.parse_args()
    
    # Set verbose mode
    TestExtractStringsFromCplusplus.set_verbose(args.verbose)
    
    if args.unittest:
        # Run using unittest framework
        unittest.main(argv=[''], exit=False, verbosity=2 if args.verbose else 1)
    else:
        # Run using custom test runner
        suite = unittest.TestLoader().loadTestsFromTestCase(TestExtractStringsFromCplusplus)
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
        result = runner.run(suite)
        
        # Exit with appropriate code
        sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
