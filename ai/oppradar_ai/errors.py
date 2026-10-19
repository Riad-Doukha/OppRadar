"""Error hierarchy for the AI package.

The backend catches ``AIRuntimeError`` for expected, explainable failures.
Anything else is a bug and may 500.
"""


class AIRuntimeError(Exception):
    """Base class for all expected AI failures."""


class FetchError(AIRuntimeError):
    """A source could not be fetched."""


class ExtractionError(AIRuntimeError):
    """LLM extraction returned something unusable."""


class CVParseError(AIRuntimeError):
    """The CV could not be read or contains no text."""


class LLMError(AIRuntimeError):
    """The LLM API failed, or is not configured."""
