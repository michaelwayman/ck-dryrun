"""Generate or verify the WP 6.8+ password hashes in fixture.sql.

    uv run --with bcrypt python docs/contracts/wp-source/mock/make_hashes.py
    uv run --with bcrypt python docs/contracts/wp-source/mock/make_hashes.py --verify

Scheme (wp-includes/pluggable.php, wp_hash_password):
    "$wp" + bcrypt(base64(HMAC-SHA384(key="wp-sha384", trim(password))))
Checked against wordpress:6.9 wp-includes/pluggable.php:2809.
PHP writes bcrypt as "$2y$"; Python's bcrypt writes "$2b$". Same algorithm.
"""

import base64
import hashlib
import hmac
import re
import sys
from pathlib import Path

import bcrypt

# Synthetic test passwords for this fixture only. Documented in README.md.
PASSWORDS = {
    "mock_admin": "mock-admin-pw-1",
    "mock_reader": "mock-reader-pw-2",
}

FIXTURE = Path(__file__).with_name("fixture.sql")


def prehash(password: str) -> bytes:
    digest = hmac.new(b"wp-sha384", password.strip().encode(), hashlib.sha384).digest()
    return base64.b64encode(digest)


def wp_hash(password: str) -> str:
    hashed = bcrypt.hashpw(prehash(password), bcrypt.gensalt(rounds=10)).decode()
    return "$wp" + hashed.replace("$2b$", "$2y$", 1)


def wp_check(password: str, stored: str) -> bool:
    if not stored.startswith("$wp$2y$"):
        return False
    return bcrypt.checkpw(prehash(password), stored[3:].replace("$2y$", "$2b$", 1).encode())


def verify() -> int:
    sql = FIXTURE.read_text()
    failures = 0
    for login, password in PASSWORDS.items():
        match = re.search(rf"'{login}', '(\$wp\$2y\$10\$[./A-Za-z0-9]{{53}})'", sql)
        ok = bool(match) and wp_check(password, match.group(1))
        print(f"{login}: {'ok' if ok else 'FAIL'}")
        failures += not ok
    return 1 if failures else 0


def main() -> int:
    if sys.argv[1:] == ["--verify"]:
        return verify()
    for login, password in PASSWORDS.items():
        print(f"{login}\t{wp_hash(password)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
