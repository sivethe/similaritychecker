# Source In Target - Boost Scoring Range Test

## Scenario
Tests the full range of boost scoring with different string length ratios to demonstrate scores below the 90% cap for "source_in_target" match types.

## Expected Behavior
- Match type: "source_in_target"
- Shows various boosted scores: ~85.7%, ~50%, 90% (capped), ~50%
- Demonstrates that the boost calculation works correctly across different ratios
- Validates that the 50% boost is applied before the 90% cap

## Test Cases
- Different source-to-target word count ratios
- Cases that result in boosted scores both above and below the 90% cap
- Comprehensive coverage of the scoring range
