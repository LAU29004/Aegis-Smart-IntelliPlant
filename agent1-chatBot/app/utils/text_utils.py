"""
app/utils/text_utils.py

WHY THIS FILE EXISTS
---------------------
Several services in this codebase truncate arbitrary text before
putting it into a log line or an exception's `details` dict (e.g.
`FollowUpQuestionService` truncating a malformed LLM response to 200
characters, `DocumentUploadPipelineService` truncating an error
message to 2000 characters before storing it on `Document.error_message`).
Each of those was a hand-rolled `text[:N]` slice with no indication
truncation actually happened. This utility centralizes that pattern
with a consistent, clearly-marked truncation suffix, making it
obvious to anyone reading a log line or a stored error message that
they're looking at a truncated excerpt, not the complete original
text.
"""


def truncate(text: str, max_length: int = 200, *, suffix: str = "... [truncated]") -> str:
    """
    Truncate `text` to at most `max_length` characters, appending
    `suffix` when truncation actually occurred.

    WHY the suffix is only appended when truncation ACTUALLY happens
    (not unconditionally appended and then the whole thing sliced):
    unconditionally appending `suffix` first and slicing afterward
    would sometimes cut the suffix itself in half, or apply it to text
    that was never actually too long to begin with - producing a
    misleading `"...[trunc"` fragment. Checking length first avoids
    that class of bug entirely.

    Args:
        text: The text to truncate.
        max_length: Maximum length of the RETURNED string, including
            the suffix when applied.
        suffix: Appended to indicate truncation occurred.

    Returns:
        `text` unchanged if it's already within `max_length`,
        otherwise a truncated prefix of `text` with `suffix` appended,
        sized so the total never exceeds `max_length`.
    """
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        # WHY this edge case matters: a caller passing an unreasonably
        # small max_length (smaller than the suffix itself) should
        # still get a bounded, valid result rather than a suffix-only
        # string longer than what they asked for.
        return suffix[:max_length]
    return text[: max_length - len(suffix)] + suffix
