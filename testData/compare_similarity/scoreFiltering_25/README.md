# Score Filtering Test (25% threshold)

## Scenario
Tests the minimum score filtering functionality with a 25% similarity threshold.

## Expected Behavior
- Only matches with similarity scores >= 25% should be included
- Lower scoring matches should be filtered out
- Validates that score filtering works correctly at the 25% threshold

## Test Cases
- Mix of high and low scoring matches
- Ensures that matches below 25% similarity are excluded from results
