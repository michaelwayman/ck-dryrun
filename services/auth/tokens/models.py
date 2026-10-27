from django.conf import settings
from django.db import models


class RefreshToken(models.Model):
    """An opaque refresh token. Only the SHA-256 of the token is stored (auth-api contract)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    # Set when the token is logged out, or when a replay revokes the user's whole family.
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Set when the token was exchanged for a new one; a second use of it is a replay.
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="refresh_expires_after_created",
            ),
        ]

    def __str__(self) -> str:
        return f"refresh token {self.pk} of user {self.user_id}"
