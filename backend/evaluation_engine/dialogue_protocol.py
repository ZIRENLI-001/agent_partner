from __future__ import annotations


ASSISTANT_DONE_MARKER = "<DONE>"
USER_END_MARKER = "<END_CONVERSATION>"
MIN_TASK_COMPLETION_MESSAGES = 5
CONTROL_MARKERS = (ASSISTANT_DONE_MARKER, USER_END_MARKER)


def parse_controlled_text(
    content: str,
    *,
    expected_marker: str,
) -> tuple[str, bool]:
    signaled = expected_marker in content
    cleaned = content
    for marker in CONTROL_MARKERS:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip(), signaled
