"""Opaque refresh tokens: issue, rotate and revoke (auth-api contract, R17)."""

import hashlib
import secrets
from datetime import datetime, timedelta

from accounts.models import User
from django.conf import settings
from django.db import transaction

from tokens.models import RefreshToken


class InvalidRefreshToken(Exception):
    """Unknown, expired, revoked or already rotated, or its user is inactive."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(user: User, now: datetime) -> str:
    """Store a new token's hash and return the token, which is never stored."""
    raw = secrets.token_urlsafe(32)  # 43 base64url characters
    RefreshToken.objects.create(
        user=user,
        token_hash=_hash(raw),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.REFRESH_TOKEN_TTL_SECONDS),
    )
    return raw


def rotate(raw: str, now: datetime) -> tuple[User, str]:
    """Spend `raw`; return its user and a new token. Replaying a spent token revokes them all."""
    with transaction.atomic():
        token = (
            RefreshToken.objects.select_for_update()
            .select_related("user")
            .filter(token_hash=_hash(raw))
            .first()
        )
        if token is None:
            raise InvalidRefreshToken
        if token.rotated_at is not None:
            RefreshToken.objects.filter(user=token.user, revoked_at__isnull=True).update(
                revoked_at=now
            )
        elif token.revoked_at is None and token.expires_at > now and token.user.is_active:
            token.rotated_at = now
            token.save(update_fields=["rotated_at"])
            return token.user, issue(token.user, now)
    # Raised outside the transaction so a replay's revocations are committed.
    raise InvalidRefreshToken


def revoke(raw: str, now: datetime) -> None:
    """Revoke `raw` if it is live. Unknown and already revoked tokens are not an error."""
    RefreshToken.objects.filter(token_hash=_hash(raw), revoked_at__isnull=True).update(
        revoked_at=now
    )
