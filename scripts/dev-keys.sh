#!/bin/sh
# Generates the dev Ed25519 signing keypair for auth (access-token contract) into $KEYS_DIR, once.
# Run by the one-shot `dev-keys` compose service; `docker compose down -v` makes it regenerate.
#   $KEYS_DIR/signing.pem               private key, PKCS8 PEM, mode 0600 (auth only)
#   $KEYS_DIR/public/kid                "dev-" + first 12 hex of SHA-256 of the public key's SPKI DER
#   $KEYS_DIR/public/public-keys.json   {"<kid>": "<public key PEM>"}, the AUTH_PUBLIC_KEYS value
# The public/ subdirectory is all the app container mounts.
set -eu

KEYS_DIR="${KEYS_DIR:-/keys}"

if [ -s "$KEYS_DIR/signing.pem" ] && [ -s "$KEYS_DIR/public/kid" ] \
    && [ -s "$KEYS_DIR/public/public-keys.json" ]; then
    echo "dev-keys: keeping existing key, kid $(cat "$KEYS_DIR/public/kid")"
    exit 0
fi

python - "$KEYS_DIR" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

keys_dir = Path(sys.argv[1])
public_dir = keys_dir / "public"
public_dir.mkdir(mode=0o755, exist_ok=True)

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()
spki_der = public_key.public_bytes(
    serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
)
kid = "dev-" + hashlib.sha256(spki_der).hexdigest()[:12]
public_pem = public_key.public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
private_pem = private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)

fd = os.open(keys_dir / "signing.pem", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "wb") as f:
    f.write(private_pem)
(public_dir / "public-keys.json").write_text(json.dumps({kid: public_pem}) + "\n")
(public_dir / "kid").write_text(kid + "\n")
print(f"dev-keys: generated a new key, kid {kid}")
PY
