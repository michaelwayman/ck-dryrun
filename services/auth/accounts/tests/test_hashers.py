import base64
import hashlib
import hmac
import os
import re
from pathlib import Path

import bcrypt
import pytest
from django.contrib.auth.hashers import check_password, identify_hasher

from accounts.hashers import WPBcryptPasswordHasher
from accounts.models import User


def wp_hash(password: str) -> str:
    """A WordPress 6.8+ hash as PHP writes it, made here at cost 4 (no vectors from the dump)."""
    prehash = base64.b64encode(
        hmac.new(b"wp-sha384", password.strip().encode(), hashlib.sha384).digest()
    )
    hashed = bcrypt.hashpw(prehash, bcrypt.gensalt(rounds=4)).decode()
    return "$wp" + hashed.replace("$2b$", "$2y$", 1)


def stored(password: str) -> str:
    return "wp_bcrypt$" + wp_hash(password)


def test_identified_by_the_text_before_the_first_dollar() -> None:
    assert isinstance(identify_hasher(stored("pw")), WPBcryptPasswordHasher)


def test_checks_a_php_2y_hash() -> None:
    encoded = stored("correct horse")
    assert "$wp$2y$04$" in encoded
    assert check_password("correct horse", encoded)
    assert not check_password("wrong horse", encoded)


def test_password_is_trimmed_like_php() -> None:
    assert check_password("  padded\t\n", stored("padded"))


@pytest.mark.parametrize(
    "encoded",
    ["wp_bcrypt$", "wp_bcrypt$$2y$04$abc", "wp_bcrypt$$wp$2a$04$abc", "wp_bcrypt$$wp$2y$garbage"],
)
def test_malformed_hashes_never_match(encoded: str) -> None:
    assert not WPBcryptPasswordHasher().verify("pw", encoded)


def test_never_makes_new_hashes() -> None:
    with pytest.raises(NotImplementedError):
        WPBcryptPasswordHasher().encode("pw", "salt")


def test_summary_masks_the_hash() -> None:
    summary = WPBcryptPasswordHasher().safe_summary(stored("pw"))
    assert summary["algorithm"] == "wp_bcrypt"
    assert "*" in summary["hash"]


@pytest.mark.django_db
def test_first_good_login_rehashes_with_the_default_hasher() -> None:
    user = User.objects.create_user("wp_user")
    user.password = stored("s3cret")
    user.save()

    assert not user.check_password("nope")
    user.refresh_from_db()
    assert user.password.startswith("wp_bcrypt$")

    assert user.check_password("s3cret")
    user.refresh_from_db()
    assert user.password.startswith("pbkdf2_sha256$")
    assert user.check_password("s3cret")


@pytest.mark.skipif(not os.environ.get("WP_DUMP_PATH"), reason="WP_DUMP_PATH (db/dump.sql) not set")
def test_real_dump_admin_hash_checks_admin() -> None:
    dump = Path(os.environ["WP_DUMP_PATH"]).read_text()
    match = re.search(r"INSERT INTO `wp_users` VALUES \(1,'admin','(\$wp\$[^']+)'", dump)
    assert match, "admin row not found in the dump"
    assert check_password("admin", "wp_bcrypt$" + match.group(1))
