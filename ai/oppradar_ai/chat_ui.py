# ipywidgets chat panel: pure HTML renderers (testable headless) plus a ChatPanel that
# only calls chat.answer() and JsonStore.append_chat() — no business logic lives here.
# ipywidgets is imported inside ChatPanel.__init__, so nothing else depends on a
# Jupyter kernel. Called by: notebooks/06_chat (same pattern as toasts.py).

from __future__ import annotations

import logging
from collections.abc import Callable
from html import escape

from oppradar_ai.chat import REFUSAL_PHRASE, answer
from oppradar_ai.config import Settings, get_settings
from oppradar_ai.schemas import (
    ChatAnswer,
    ChatTurn,
    Citation,
    EligibilityAssessment,
    Opportunity,
    Profile,
)
from oppradar_ai.store import JsonStore

logger = logging.getLogger(__name__)

_BUBBLES = {
    "user": ("You", "#e3f2fd"),
    "assistant": ("Assistant", "#f5f5f5"),
}
_VERDICTS = {
    True: ("Looks eligible", "#2e7d32"),
    False: ("Not eligible yet", "#c62828"),
    None: ("Not enough information", "#f57f17"),
}


def bubble_html(role: str, content: str) -> str:
    """One chat bubble: who spoke and the (escaped) text, line breaks kept.

    Example:
        >>> html = bubble_html("user", "Deadline <b>?")
        >>> "You" in html, "&lt;b&gt;" in html
        (True, True)
    """
    label, color = _BUBBLES.get(role, _BUBBLES["assistant"])
    text = escape(content).replace("\n", "<br>")
    return (
        f'<div style="background:{color};border-radius:8px;padding:6px 10px;margin:4px 0;">'
        f"<b>{label}</b><br>{text}</div>"
    )


def turn_html(turn: ChatTurn) -> str:
    """A stored turn as a bubble (stored turns carry text only).

    Example:
        >>> "Assistant" in turn_html(ChatTurn(role="assistant", content="Hi"))
        True
    """
    return bubble_html(turn.role, turn.content)


def citations_html(citations: list[Citation]) -> str:
    """The sources block: a link to the page and the quoted phrase, or '' when none.

    Example:
        >>> citations_html([])
        ''
        >>> "example.org" in citations_html([Citation(url="https://example.org/a", title="A")])
        True
    """
    if not citations:
        return ""
    items = "".join(f"<li>{_citation_item(citation)}</li>" for citation in citations)
    return (
        '<div style="font-size:90%;margin:2px 0 4px 8px;"><b>Sources</b>'
        f"<ul style='margin:2px 0 0 16px;padding:0;'>{items}</ul></div>"
    )


def eligibility_html(assessment: EligibilityAssessment | None) -> str:
    """The eligibility box: verdict, requirements met, gaps and next steps ('' if none).

    Example:
        >>> eligibility_html(None)
        ''
        >>> "Not eligible yet" in eligibility_html(EligibilityAssessment(eligible=False))
        True
    """
    if assessment is None:
        return ""
    label, color = _VERDICTS[assessment.eligible]
    rows = [f"<li>✓ {escape(text)}</li>" for text in assessment.met]
    rows += [f"<li>✗ {escape(text)}</li>" for text in assessment.gaps]
    rows += [f"<li>→ {escape(text)}</li>" for text in assessment.next_steps]
    return (
        f'<div style="border-left:4px solid {color};padding:2px 8px;margin:4px 0 4px 8px;">'
        f'<b style="color:{color};">{label}</b>'
        f"<ul style='margin:2px 0 0 16px;padding:0;'>{''.join(rows)}</ul></div>"
    )


def answer_html(reply: ChatAnswer) -> str:
    """The assistant's reply: bubble, 'not in the source' badge, sources, eligibility.

    Example:
        >>> reply = ChatAnswer(answer="That is not in the source.", in_source=False)
        >>> "not in the source" in answer_html(reply)
        True
    """
    parts = [bubble_html("assistant", reply.answer)]
    if not reply.in_source:
        parts.append(
            f'<div style="color:#f57f17;margin-left:8px;">⚠ {escape(REFUSAL_PHRASE)}: '
            "check the official page.</div>"
        )
    if reply.extracted_opportunity is not None:
        parts.append(_extracted_html(reply.extracted_opportunity))
    parts += [citations_html(reply.citations), eligibility_html(reply.eligibility)]
    return "".join(parts)


def header_html(opportunity: Opportunity | None) -> str:
    """What the conversation is about right now.

    Example:
        >>> "No opportunity" in header_html(None)
        True
    """
    if opportunity is None:
        return "<b>No opportunity selected</b> — paste an announcement or a link."
    deadline = f" — deadline {opportunity.deadline}" if opportunity.deadline else ""
    name = f"{escape(opportunity.title)} · {escape(opportunity.organizer)}"
    return f"<b>Chatting about:</b> {name}{deadline}"


def _citation_item(citation: Citation) -> str:
    title = escape(citation.title or citation.url or "source")
    href = _safe_href(citation.url)
    link = title
    if href:
        link = f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener">{title}</a>'
    quote = f" — “{escape(citation.quote)}”" if citation.quote else ""
    return f"{link}{quote}"


def _extracted_html(opportunity: Opportunity) -> str:
    return (
        '<div style="margin-left:8px;color:#1565c0;">Read from your message: '
        f"<b>{escape(opportunity.title)}</b> · {escape(opportunity.organizer)}</div>"
    )


def _safe_href(url: str) -> str:
    """Only http(s) links become clickable (a record's URL is untrusted text)."""
    return url if url.startswith(("http://", "https://")) else ""


class ChatPanel:
    """A scrollable transcript, a text box and a Send button around chat.answer().

    Turns are stored only through `store.append_chat`; reopening a panel for the
    same profile shows the stored conversation again. A pasted announcement or
    link switches the panel to the opportunity extracted from it.

    Example:
        >>> panel = ChatPanel(profile, opportunity, store)       # doctest: +SKIP
        >>> reply = panel.send("What is the deadline?")          # doctest: +SKIP
        >>> reply.in_source
        True
    """

    def __init__(
        self,
        profile: Profile,
        opportunity: Opportunity | None,
        store: JsonStore,
        *,
        settings: Settings | None = None,
        answer_fn: Callable[..., ChatAnswer] = answer,
        max_visible: int = 50,
    ) -> None:
        try:
            import ipywidgets as widgets
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise RuntimeError("ChatPanel needs ipywidgets (pip install ipywidgets)") from exc
        self._widgets = widgets
        self.profile = profile
        self.opportunity = opportunity
        self.store = store
        self.settings = settings or get_settings()
        self.max_visible = max_visible
        self._answer_fn = answer_fn
        self._blocks: list[str] = []
        self._build()
        self._load_history()

    def send(self, text: str) -> ChatAnswer | None:
        """Ask one question: answer it, store both turns, show them (None for empty text)."""
        text = text.strip()
        if not text:
            return None
        user_id = self.profile.user_id
        history = self.store.chat_history(user_id, limit=self.settings.chat_history_turns)
        self._set_status("thinking…")
        try:
            reply = self._answer_fn(
                self.profile, self.opportunity, history, text, settings=self.settings
            )
        finally:
            self._set_status("")
        self.store.append_chat(user_id, ChatTurn(role="user", content=text))
        self.store.append_chat(user_id, ChatTurn(role="assistant", content=reply.answer))
        self._append(bubble_html("user", text))
        self._append(answer_html(reply))
        if reply.extracted_opportunity is not None:
            self.set_opportunity(reply.extracted_opportunity)
        return reply

    def set_opportunity(self, opportunity: Opportunity | None) -> None:
        """Switch what the conversation is about (stored history is kept)."""
        self.opportunity = opportunity
        self.header.value = header_html(opportunity)

    def clear(self) -> None:
        """Empty the visible transcript (the stored history is kept)."""
        self._blocks = []
        self.log.value = ""

    # -- widget plumbing ----------------------------------------------------- #
    def _build(self) -> None:
        widgets = self._widgets
        self.header = widgets.HTML(value=header_html(self.opportunity))
        self.log = widgets.HTML(
            layout=widgets.Layout(
                height="320px", overflow_y="auto", border="1px solid #ddd", padding="4px"
            )
        )
        self.status = widgets.HTML()
        self.box = widgets.Textarea(
            placeholder="Ask about this opportunity…", rows=2, layout=widgets.Layout(width="75%")
        )
        self.send_button = widgets.Button(description="Send", button_style="primary")
        self.clear_button = widgets.Button(description="Clear view")
        self.send_button.on_click(self._on_send)
        self.clear_button.on_click(self._on_clear)
        controls = widgets.HBox([self.box, self.send_button, self.clear_button])
        self.container = widgets.VBox([self.header, self.log, self.status, controls])

    def _load_history(self) -> None:
        limit = self.settings.chat_history_turns
        for turn in self.store.chat_history(self.profile.user_id, limit=limit):
            self._append(turn_html(turn))

    def _append(self, block: str) -> None:
        self._blocks.append(block)
        self.log.value = "".join(self._blocks[-self.max_visible :])

    def _set_status(self, text: str) -> None:
        self.status.value = f"<i>{escape(text)}</i>" if text else ""

    def _on_send(self, _button: object) -> None:
        """Send-button callback: a failure is shown, never raised into the kernel."""
        try:
            if self.send(self.box.value) is not None:
                self.box.value = ""
        except Exception as exc:  # a dead widget must never take anything down
            logger.exception("chat panel: send failed")
            self._set_status(f"Something went wrong ({type(exc).__name__}); try again.")

    def _on_clear(self, _button: object) -> None:
        try:
            self.clear()
        except Exception:
            logger.exception("chat panel: clear failed")
