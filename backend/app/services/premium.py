"""Premium early access. Payments are not live: a reservation records the plan
the user wants (and the payment method they'd prefer) and their place in the
queue. Nothing is charged and no payment details are collected."""

from __future__ import annotations

from app.auth import CurrentUser
from app.models import PremiumStatus, Reservation, ReservationIn
from app.repositories import Repository
from app.repositories.base import Row
from app.services.parallel import gather


def _reservation(repo: Repository, row: Row) -> Reservation:
    return Reservation.model_validate(
        {**row, "position": repo.count_reservations(row["created_at"])}
    )


def status(repo: Repository, user: CurrentUser) -> PremiumStatus:
    r = gather(mine=lambda: repo.get_reservation(user.id), total=lambda: repo.count_reservations())
    return PremiumStatus(
        reservation=_reservation(repo, r["mine"]) if r["mine"] else None,
        reservations_total=r["total"],
    )


def reserve(repo: Repository, user: CurrentUser, body: ReservationIn) -> PremiumStatus:
    """Create or change the reservation; the queue position stays (created_at is kept)."""
    repo.upsert_reservation(user.id, body.model_dump())
    return status(repo, user)


def cancel(repo: Repository, user: CurrentUser) -> PremiumStatus:
    repo.delete_reservation(user.id)
    return status(repo, user)
