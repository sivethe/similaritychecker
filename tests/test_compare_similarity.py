#!/usr/bin/env python3
"""
Testing framework for compare_json_similarity_fast.py

This script runs compare_json_similarity_fast.py against test files in the testData/ directory
and validates the substring matching functionality.

Usage:
    python3 test_compare_similarity.py              # Run all tests
    python3 test_compare_similarity.py --verbose    # Run with detailed output
    python3 test_compare_similarity.py --update     # Update expected results
    python3 test_compare_similarity.py --test sourceSubstring  # Run specific test
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", expected_count: int = 0, actual_count: int = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.expected_count = expected_count
        self.actual_count = actual_count

class SimilarityTestFramework:
    def __init__(self, test_dir: str = "testData/compare_similarity", similarity_script: str = "compare_json_similarity_fast.py"):
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
            
        self.similarity_script = Path(similarity_script)
        # If similarity_script is relative, make it relative to project root
        if not self.similarity_script.is_absolute():
            self.similarity_script = project_root / self.similarity_script
        
        self.test_results: List[TestResult] = []
        
        # Validate paths
        if not self.test_dir.exists():
            raise FileNotFoundError(f"Test directory not found: {self.test_dir}")
        if not self.similarity_script.exists():
            raise FileNotFoundError(f"Similarity script not found: {self.similarity_script}")
    
    def discover_test_files(self) -> List[Tuple[Path, Path, str]]:
        """Discover test file pairs (source, target) in test subdirectories."""
        test_pairs = []
        
        # Look for subdirectories containing source.json and target.json
        for test_subdir in self.test_dir.iterdir():
            if test_subdir.is_dir():
                source_file = test_subdir / "source.json"
                target_file = test_subdir / "target.json"
                
                if source_file.exists() and target_file.exists():
                    test_pairs.append((source_file, target_file, test_subdir.name))
                else:
                    missing_files = []
                    if not source_file.exists():
                        missing_files.append("source.json")
                    if not target_file.exists():
                        missing_files.append("target.json")
                    print(f"⚠️  Warning: Missing files in {test_subdir.name}: {', '.join(missing_files)}")
        
        return sorted(test_pairs, key=lambda x: x[2])  # Sort by test name
    
    def get_expected_output_file(self, source_file: Path) -> Path:
        """Get the expected output file path for a test."""
        # Expected file is in the same directory as source file, named expected.json
        return source_file.parent / "expected.json"
    
    def load_test_config(self, test_dir: Path) -> Dict[str, Any]:
        """Load test configuration from test_config.json if it exists."""
        config_file = test_dir / "test_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Warning: Error loading test config from {config_file}: {e}")
        return {}
    
    def run_similarity_script(self, source_file: Path, target_file: Path, min_words: int = 4, min_score: float = None, test_config: Dict[str, Any] = None, verbose: bool = False) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """Run the similarity script and return the results."""
        temp_output_path = None
        try:
            # Create temporary output file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                temp_output_path = temp_file.name
            
            # Apply test configuration if provided
            if test_config is None:
                test_config = {}
            
            # Override with test config values
            if min_score is None and 'min_score' in test_config:
                min_score = test_config['min_score']
            
            # Build command
            cmd = [
                sys.executable,
                str(self.similarity_script),
                str(source_file),
                str(target_file),
                "--min-words", str(min_words),
                "--output", temp_output_path
            ]
            
            # Add min-score parameter if specified
            if min_score is not None:
                cmd.extend(["--min-score", str(min_score)])
            
            if verbose:
                print(f"Running: {' '.join(cmd)}")
                if test_config:
                    print(f"Test config: {test_config}")
            
            # Execute the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.similarity_script.parent
            )
            
            if result.returncode != 0:
                error_msg = f"Script failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                return False, error_msg, None
            
            # Load the output
            try:
                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    output_data = json.load(f)
                return True, "", output_data
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON output: {e}", None
            except Exception as e:
                return False, f"Error reading output: {e}", None
        
        except Exception as e:
            return False, f"Error running script: {e}", None
        
        finally:
            # Clean up temp file
            if temp_output_path:
                try:
                    os.unlink(temp_output_path)
                except:
                    pass
    
    def load_expected_output(self, expected_file: Path) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
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
    
    def compare_outputs(self, expected: List[Dict[str, Any]], actual: List[Dict[str, Any]], test_name: str) -> TestResult:
        """Compare expected and actual outputs."""
        # Basic count comparison
        if len(expected) != len(actual):
            return TestResult(
                test_name,
                False,
                f"❌ FAIL: Different number of matches (expected {len(expected)}, got {len(actual)})",
                len(expected),
                len(actual)
            )
        
        # Detailed comparison
        for i, (exp_match, act_match) in enumerate(zip(expected, actual)):
            # Compare source indices
            if exp_match.get("source_index") != act_match.get("source_index"):
                return TestResult(
                    test_name,
                    False,
                    f"❌ FAIL: Source index mismatch at match {i} (expected {exp_match.get('source_index')}, got {act_match.get('source_index')})",
                    len(expected),
                    len(actual)
                )
            
            # Compare match counts
            exp_count = exp_match.get("match_count", 0)
            act_count = act_match.get("match_count", 0)
            if exp_count != act_count:
                return TestResult(
                    test_name,
                    False,
                    f"❌ FAIL: Match count mismatch for source {exp_match.get('source_index')} (expected {exp_count}, got {act_count})",
                    len(expected),
                    len(actual)
                )
            
            # Compare target matches (basic check - at least same number)
            exp_targets = exp_match.get("target_matches", [])
            act_targets = act_match.get("target_matches", [])
            
            if len(exp_targets) != len(act_targets):
                return TestResult(
                    test_name,
                    False,
                    f"❌ FAIL: Target match count mismatch for source {exp_match.get('source_index')} (expected {len(exp_targets)}, got {len(act_targets)})",
                    len(expected),
                    len(actual)
                )
        
        return TestResult(
            test_name, 
            True, 
            f"✅ PASS: All matches validated ({len(actual)} source matches)",
            len(expected),
            len(actual)
        )
    
    def validate_match_structure(self, matches: List[Dict[str, Any]], test_name: str) -> TestResult:
        """Validate the structure of match results."""
        required_fields = ["source_index", "source_line", "target_matches", "match_count"]
        target_match_fields = ["target_index", "similarity_score", "target_line", "match_type", "matched_text"]
        
        for i, match in enumerate(matches):
            # Check required fields in main match
            for field in required_fields:
                if field not in match:
                    return TestResult(
                        test_name,
                        False,
                        f"❌ FAIL: Missing field '{field}' in match {i}",
                        0, len(matches)
                    )
            
            # Check target matches structure
            target_matches = match.get("target_matches", [])
            for j, target_match in enumerate(target_matches):
                for field in target_match_fields:
                    if field not in target_match:
                        return TestResult(
                            test_name,
                            False,
                            f"❌ FAIL: Missing field '{field}' in target match {j} of source match {i}",
                            0, len(matches)
                        )
                
                # Validate match_type values
                valid_match_types = ["source_in_target", "target_in_source", "source_combo_in_target", "target_combo_in_source", "exact_match", "format_specifier_match", "reverse_format_specifier_match"]
                match_type = target_match.get("match_type")
                if match_type not in valid_match_types:
                    return TestResult(
                        test_name,
                        False,
                        f"❌ FAIL: Invalid match_type '{match_type}' in target match {j} of source match {i}",
                        0, len(matches)
                    )
        
        return TestResult(
            test_name,
            True,
            f"✅ PASS: Structure validation passed ({len(matches)} matches)",
            0, len(matches)
        )
    
    def update_expected_output(self, source_file: Path, output_data: List[Dict[str, Any]]) -> bool:
        """Update the expected output file for a test."""
        expected_file = self.get_expected_output_file(source_file)
        try:
            with open(expected_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error updating expected output for {source_file.name}: {e}")
            return False
    
    def run_single_test(self, source_file: Path, target_file: Path, test_name: str, verbose: bool = False, update_expected: bool = False, min_words: int = 4) -> List[TestResult]:
        """Run a single test case."""
        results = []
        
        if verbose:
            print(f"\n🧪 Running test: {test_name}")
        
        # Load test configuration
        test_config = self.load_test_config(source_file.parent)
        
        # Run the similarity script
        success, error_msg, actual_output = self.run_similarity_script(source_file, target_file, min_words, None, test_config, verbose)
        if not success:
            results.append(TestResult(test_name, False, f"❌ FAIL: {error_msg}"))
            return results
        
        # Validate structure first
        structure_result = self.validate_match_structure(actual_output, f"{test_name}_structure")
        results.append(structure_result)
        
        if update_expected:
            # Update mode: save the current output as expected
            if self.update_expected_output(source_file, actual_output):
                results.append(TestResult(f"{test_name}_update", True, f"📝 UPDATED: Expected output saved ({len(actual_output)} matches)"))
            else:
                results.append(TestResult(f"{test_name}_update", False, "❌ FAIL: Could not update expected output"))
            return results
        
        # Test mode: compare with expected output
        expected_file = self.get_expected_output_file(source_file)
        success, error_msg, expected_output = self.load_expected_output(expected_file)
        if not success:
            results.append(TestResult(f"{test_name}_comparison", False, f"❌ FAIL: {error_msg}"))
            return results
        
        comparison_result = self.compare_outputs(expected_output, actual_output, f"{test_name}_comparison")
        results.append(comparison_result)
        
        return results
    
    def run_all_tests(self, verbose: bool = False, update_expected: bool = False, specific_test: Optional[str] = None, min_words: int = 4) -> None:
        """Run all tests or a specific test."""
        test_pairs = self.discover_test_files()
        
        if specific_test:
            # Filter to specific test
            test_pairs = [(s, t, n) for s, t, n in test_pairs if specific_test.lower() in n.lower()]
            if not test_pairs:
                print(f"❌ No test files found matching: {specific_test}")
                return
        
        if not test_pairs:
            print("❌ No test file pairs found in test directory")
            return
        
        print(f"🔍 Found {len(test_pairs)} test pair(s)")
        sys.stdout.flush()
        if update_expected:
            print("📝 Update mode: Will update expected outputs")
            sys.stdout.flush()
        
        for source_file, target_file, test_name in test_pairs:
            test_results = self.run_single_test(source_file, target_file, test_name, verbose, update_expected, min_words)
            self.test_results.extend(test_results)
            
            if not verbose:
                # Show concise output
                for result in test_results:
                    status = "✅" if result.passed else "❌"
                    print(f"{status} {result.name}")
                    sys.stdout.flush()
            else:
                for result in test_results:
                    print(f"\n{result.message}")
                    sys.stdout.flush()
    
    def print_summary(self) -> None:
        """Print a summary of all test results."""
        if not self.test_results:
            return
        
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        
        print(f"\n{'='*60}")
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
        sys.stdout.flush()
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print(f"\n❌ Failed tests:")
            for result in self.test_results:
                if not result.passed:
                    print(f"  • {result.name}: {result.message}")
        
        print(f"{'='*60}")
        sys.stdout.flush()
    
    def has_failures(self) -> bool:
        """Check if any tests failed."""
        return any(not r.passed for r in self.test_results)

def main():
    parser = argparse.ArgumentParser(
        description="Test framework for compare_json_similarity_fast.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 test_compare_similarity.py                    # Run all tests
  python3 test_compare_similarity.py --verbose          # Run with detailed output
  python3 test_compare_similarity.py --update           # Update expected results
  python3 test_compare_similarity.py --test sourceSubstring   # Run specific test
  python3 test_compare_similarity.py --min-words 3      # Test with 3-word minimum
        """
    )
    
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose output")
    parser.add_argument("--update", action="store_true",
                       help="Update expected output files instead of testing")
    parser.add_argument("--test", type=str,
                       help="Run specific test (partial name match)")
    parser.add_argument("--min-words", type=int, default=4,
                       help="Minimum word combination length for testing (default: 4)")
    parser.add_argument("--test-dir", default="testData/compare_similarity",
                       help="Directory containing test files (default: testData/compare_similarity)")
    parser.add_argument("--script", default="compare_json_similarity_fast.py",
                       help="Path to compare_json_similarity_fast.py script (default: compare_json_similarity_fast.py)")
    
    args = parser.parse_args()
    
    try:
        framework = SimilarityTestFramework(args.test_dir, args.script)
        framework.run_all_tests(args.verbose, args.update, args.test, args.min_words)
        framework.print_summary()
        
        # Exit with error code if tests failed
        if framework.has_failures() and not args.update:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
