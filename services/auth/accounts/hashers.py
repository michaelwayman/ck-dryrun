"""Checks WordPress 6.8+ `$wp$2y$` password hashes (T5) so imported users keep their passwords.

Stored as `wp_bcrypt$` + the WP hash, e.g. `wp_bcrypt$$wp$2y$10$…`. Django finds the hasher from
the text before the first `$`. WP's scheme (wp-includes/pluggable.php, wp_hash_password):
`"$wp" + bcrypt(base64(HMAC-SHA384(key="wp-sha384", trim(password))))`.
"""

import base64
import hashlib
import hmac
from typing import Any

import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.utils.translation import gettext_noop as _

WP_PREFIX = "$wp"
# The characters PHP's trim() strips, which is narrower than str.strip()'s Unicode whitespace.
PHP_TRIM = " \t\n\r\0\x0b"


class WPBcryptPasswordHasher(BasePasswordHasher):
    """Verify-only: listed after Django's default, so a successful check re-hashes with that."""

    algorithm = "wp_bcrypt"

    def verify(self, password: str, encoded: str) -> bool:
        bcrypt_hash = self._bcrypt_hash(encoded)
        if bcrypt_hash is None:
            return False
        try:
            return bcrypt.checkpw(_prehash(password), bcrypt_hash.encode("ascii"))
        except ValueError:  # malformed bcrypt string
            return False

    def encode(self, password: str, salt: str) -> str:
        raise NotImplementedError(
            "wp_bcrypt only verifies imported hashes; it never makes new ones."
        )

    def safe_summary(self, encoded: str) -> dict[Any, Any]:
        bcrypt_hash = self._bcrypt_hash(encoded) or ""
        return {_("algorithm"): self.algorithm, _("hash"): mask_hash(bcrypt_hash)}

    def must_update(self, encoded: str) -> bool:
        return True

    def harden_runtime(self, password: str, encoded: str) -> None:
        pass  # must_update is always true, so Django re-hashes instead of calling this

    def _bcrypt_hash(self, encoded: str) -> str | None:
        """The bcrypt part of `wp_bcrypt$$wp$2y$…`, with PHP's `$2y$` as Python's `$2b$`."""
        algorithm, _sep, wp_hash = encoded.partition("$")
        if algorithm != self.algorithm or not wp_hash.startswith(WP_PREFIX + "$2y$"):
            return None
        return "$2b$" + wp_hash.removeprefix(WP_PREFIX + "$2y$")


def _prehash(password: str) -> bytes:
    digest = hmac.new(b"wp-sha384", password.strip(PHP_TRIM).encode(), hashlib.sha384).digest()
    return base64.b64encode(digest)
