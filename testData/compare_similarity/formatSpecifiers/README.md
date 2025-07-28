# Format Specifiers Test

## Scenario
Tests C printf-style format specifier matching functionality where strings contain format placeholders like %s, %d, %f, etc.

## Expected Behavior
- Match type: "format_specifier_match" or "reverse_format_specifier_match"
- Similarity scores based on literal content vs format specifiers ratio
- Format specifiers should match against actual values in target strings

## Test Cases
- Strings with various format specifiers (%s, %d, %f, etc.)
- Validates that format specifier patterns correctly match target content
- Tests both forward and reverse format specifier matching
