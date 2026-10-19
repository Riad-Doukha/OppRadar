"""Chat assistant: retrieval → grounded answer.

    from oppradar_ai.chat import ask
    response = ask("any remote ML internships?", profile=profile)
"""

from oppradar_ai.chat.assistant import ask
from oppradar_ai.chat.retrieval import OpportunityIndex

__all__ = ["ask", "OpportunityIndex"]
