package com.yuy.eduflow.adjustment;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record AdjustmentSuggestionCandidate(
    int candidateIndex,
    String summary,
    Long newTimeSlotId,
    Long newClassroomId
) {}
