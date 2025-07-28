# Score Filtering Test (50% threshold)

## Scenario
Tests the minimum score filtering functionality with a 50% similarity threshold.

## Expected Behavior
- Only matches with similarity scores >= 50% should be included
- Lower scoring matches should be filtered out
- Validates that score filtering works correctly at the 50% threshold

## Test Cases
- Mix of high and low scoring matches
- Ensures that matches below 50% similarity are excluded from results
