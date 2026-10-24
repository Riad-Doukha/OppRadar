# ipywidgets toast board: the moment a match passes the notification rules, a
# small card pops up in the notebook — title (a link to the source), score and
# the top reasons — and can be dismissed. ipywidgets is imported inside the
# functions, so the rest of the pipeline never depends on a Jupyter kernel.
# Called by: notebooks/08_background_agent (wired to BackgroundAgent callbacks).

from __future__ import annotations

import logging
from html import escape

from oppradar_ai.schemas import MatchResult, Notification

logger = logging.getLogger(__name__)


def toast_html(notification: Notification, match: MatchResult | None = None) -> str:
    """The toast card: title link, score badge, top reasons, deadline line.

    Example:
        >>> from datetime import date
        >>> note = Notification(profile_id="u", opportunity_id="o",
        ...                     title="ML Intern", score=85.0,
        ...                     url="https://x.org/ml", deadline=date(2027, 1, 1))
        >>> html = toast_html(note)
        >>> "ML Intern" in html, "85.0/100" in html
        (True, True)
    """
    reasons = list(match.top_reasons) if match else []
    if not reasons and notification.reason:
        reasons = [notification.reason]
    title = escape(notification.title)
    link = (
        f'<a href="{escape(notification.url, quote=True)}" target="_blank" '
        f'rel="noopener">{title}</a>'
        if notification.url
        else title
    )
    bullets = "".join(f"<li>{escape(reason)}</li>" for reason in reasons)
    deadline = (
        f"<div>Deadline: {notification.deadline}</div>" if notification.deadline else ""
    )
    color = _score_color(notification.score)
    return (
        f'<div style="border-left:4px solid {color};padding:4px 8px;">'
        f"<b>{link}</b> "
        f'<span style="color:{color};">{notification.score:.1f}/100</span>'
        f"<ul style='margin:4px 0 0 16px;padding:0;'>{bullets}</ul>{deadline}</div>"
    )


def _score_color(score: float) -> str:
    """Border/badge colour: green for the best, amber for the rest."""
    return "#2e7d32" if score >= 85 else "#f57f17"


class ToastBoard:
    """A VBox of dismissible toasts; push() is safe from the agent's thread.

    The agent is never imported here: the notebook wires the two with
    `agent.add_notification_callback(board.push)`.

    Example:
        >>> board = ToastBoard()                       # doctest: +SKIP
        >>> board.push(notification, match)            # doctest: +SKIP
        >>> len(board.container.children)
        1
    """

    def __init__(self, *, max_visible: int = 5) -> None:
        try:
            import ipywidgets as widgets
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise RuntimeError("ToastBoard needs ipywidgets (pip install ipywidgets)") from exc
        self._widgets = widgets
        self.max_visible = max_visible
        self.container = widgets.VBox()
        self.delivered: list[Notification] = []

    def push(self, notification: Notification, match: MatchResult | None = None) -> None:
        """Pop one toast card (the agent calls this for every SENT row)."""
        self.delivered.append(notification)
        widgets = self._widgets
        card = widgets.HTML(value=toast_html(notification, match))
        dismiss = widgets.Button(
            description="dismiss",
            tooltip="close this toast",
            layout=widgets.Layout(width="72px"),
        )
        row = widgets.HBox([card, dismiss])

        def _on_click(_button: object) -> None:
            self._drop(row)

        dismiss.on_click(_on_click)
        self.container.children = (*self.container.children, row)
        while len(self.container.children) > self.max_visible:
            self._drop(self.container.children[0])
        logger.info("toast: %s (%.1f/100)", notification.title, notification.score)

    def clear(self) -> None:
        """Remove every visible toast (the delivered history is kept)."""
        self.container.children = ()

    def _drop(self, row: object) -> None:
        self.container.children = tuple(c for c in self.container.children if c is not row)
