# Target In Source - Boost Scoring Test

## Scenario
Tests the enhanced similarity scoring logic with 50% boost (capped at 90%) for "target_in_source" match types where target strings are contained within source strings.

## Expected Behavior
- Match type: "target_in_source"
- Base scores calculated as (target_words / source_words) * 100
- Boosted scores: base_score * 1.5, capped at 90%
- Expected scores: 90% (capped), 60%, 60%

## Test Cases
- Target strings that are shorter than and contained within source strings
- Demonstrates boost scoring for the reverse scenario (target in source)
- Validates correct identification and scoring of "target_in_source" matches
