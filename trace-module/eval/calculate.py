from typing import Dict, List


def binarize_predictions(predictions: Dict[str, float], threshold: float = 0.5) -> Dict[str, int]:
    return {label: 1 if conf >= threshold else 0 for label, conf in predictions.items()}


def labels_to_states(labels: List[Dict[str, int]]) -> List[str]:
    """
    Convert per-sentence binary label dicts into compound state strings.
    No consecutive-duplicate compression is applied; every sentence yields one state.
    Active labels are joined alphabetically with '+', empty labels become 'EMPTY'.
    """
    if not labels:
        return []

    def to_compound_state(label_dict):
        active = sorted([label for label, value in label_dict.items() if value == 1])
        return '+'.join(active) if active else 'EMPTY'

    return [to_compound_state(label_dict) for label_dict in labels]


GOOD_TRANSITIONS = {
    ("Data/Evidence", "Claim"),
    ("Warrant", "Claim"),
    ("Claim", "Backing"),
    ("Backing", "Claim"),
    ("Backing", "Evaluation"),
    ("Claim", "Evaluation"),
    ("Data/Evidence", "Warrant"),
    ("Monitoring", "Claim"),
    ("Monitoring", "Data/Evidence"),
    ("Monitoring", "Backing"),
    ("Monitoring", "Evaluation"),
    ("Rebuttal", "Claim"),
    ("Rebuttal", "Backing"),
}

BAD_TRANSITIONS = {
    ("Monitoring", "Monitoring"),
    ("Qualifier", "Qualifier"),
    ("Monitoring", "Qualifier"),
    ("Qualifier", "Monitoring"),
    ("Rebuttal", "Rebuttal"),
    ("Rebuttal", "Qualifier"),
    ("Qualifier", "Rebuttal"),
}


ALLOWED_STATES = {
    'Claim', 'Claim+Data/Evidence', 'Claim+Evaluation',
    'Data/Evidence', 'Data/Evidence+Warrant',
    'Warrant', 'Warrant+Backing',
    'Backing', 'Backing+Evaluation',
    'Evaluation',
}


def calculate_state_validity(states: List[str]) -> float:
    """
    State Validity (V_state): how well each sentence's label set matches an
    allowed Toulmin/Flavell construct. EMPTY states are included in the average.
    Falls back to Jaccard overlap when no exact match exists.
    Returns a score in [0, 1].
    """
    if not states:
        return 0.0

    match_score = 0.0

    for state in states:
        if state in ALLOWED_STATES:
            match_score += 1.0
            continue

        actual_labels = set(state.split('+'))
        best_overlap = 0.0
        for allowed_state in ALLOWED_STATES:
            allowed_labels = set(allowed_state.split('+'))
            intersection = len(actual_labels & allowed_labels)
            union = len(actual_labels | allowed_labels)
            overlap = intersection / union if union > 0 else 0.0
            best_overlap = max(best_overlap, overlap)
        match_score += best_overlap

    return match_score / len(states)


def calculate_transition_coherence(states: List[str]) -> float:
    """
    Transition Coherence (C_trans): density of good vs. bad transitions across
    adjacent non-empty states. Multi-label states contribute every pairwise
    (from_label, to_label) transition.
    Returns a score in [-1, 1] (positive = more good transitions).
    """
    if len(states) < 2:
        return 0.0

    non_empty_states = [state for state in states if state != 'EMPTY']
    if len(non_empty_states) < 2:
        return 0.0

    good_count = 0
    bad_count = 0
    total_transitions = 0

    for i in range(len(non_empty_states) - 1):
        from_labels = non_empty_states[i].split('+')
        to_labels = non_empty_states[i + 1].split('+')

        for from_label in from_labels:
            for to_label in to_labels:
                pair = (from_label, to_label)
                if pair in GOOD_TRANSITIONS:
                    good_count += 1
                elif pair in BAD_TRANSITIONS:
                    bad_count += 1
                total_transitions += 1

    if total_transitions == 0:
        return 0.0

    return (good_count - bad_count) / total_transitions


def calculate_trace_from_labels(
    labels: List[Dict[str, int]],
    alpha: float = 0.7,
) -> float:
    """
    TRACE score: weighted combination of State Validity and Transition Coherence.

        TRACE = alpha * V_state + (1 - alpha) * C_trans_normalized

    State Validity is in [0, 1]; Transition Coherence is in [-1, 1] and is
    linearly rescaled to [0, 1] before being mixed in.

    Args:
        labels: List of binary label dicts (one per sentence).
        alpha: State Validity weight. Defaults to 0.7 per the TRACE paper.

    Returns:
        TRACE score in [0, 1].
    """
    if not labels:
        return 0.0

    states = labels_to_states(labels)
    if not states:
        return 0.0

    state_validity = calculate_state_validity(states)
    transition_coherence = calculate_transition_coherence(states)
    transition_coherence_normalized = (transition_coherence + 1) / 2

    trace_score = alpha * state_validity + (1 - alpha) * transition_coherence_normalized
    return trace_score
