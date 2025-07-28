# Source In Target - Boost Scoring Test

## Scenario
Tests the enhanced similarity scoring logic with 50% boost (capped at 90%) for "source_in_target" match types where all cases hit the 90% cap.

## Expected Behavior
- Match type: "source_in_target"
- Base scores calculated as (source_words / target_words) * 100
- Boosted scores: base_score * 1.5, capped at 90%
- All test cases should show similarity scores of 90% due to the cap

## Test Cases
- Source strings contained within longer target strings
- Various string lengths that result in boosted scores exceeding 90%
- Validates that the 90% cap is properly applied
