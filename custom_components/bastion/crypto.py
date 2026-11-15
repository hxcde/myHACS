"""Encryption of secret files before they are pushed to git.

Scheme
------
* A 64 byte key is derived from the passphrase with scrypt and a random salt.
  The first 32 bytes are the AES-256-GCM key, the last 32 bytes a HMAC key.
* Every file is encrypted with a random 96 bit nonce. The repository path is
  bound as associated data, so an encrypted blob cannot be moved to another
  path without detection.
* A keyed HMAC of path and plaintext lets the sync detect unchanged files
  without decrypting them and without leaking hashes of low entropy secrets.

Blob format (version 2, ASCII armored so it displays cleanly on GitHub)::

    -----BEGIN BASTION ENCRYPTED FILE-----
    Version: 2
    Path: homeassistant/secrets.yaml

    base64( MAGIC || nonce(12) || ciphertext+tag ), 76 chars per line
    -----END BASTION ENCRYPTED FILE-----

Version 1 (the raw binary payload without armor) is still decrypted.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"BASTION1"
NONCE_LEN = 12
ARMOR_BEGIN = b"-----BEGIN BASTION ENCRYPTED FILE-----"
ARMOR_END = b"-----END BASTION ENCRYPTED FILE-----"
FORMAT_VERSION = 2
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


class DecryptionError(Exception):
    """Raised when a blob cannot be decrypted (wrong passphrase or tampered)."""


def new_salt() -> str:
    """Return a new random salt (base64)."""
    return base64.b64encode(os.urandom(16)).decode()


@dataclass(frozen=True, slots=True)
class FileCipher:
    """Encrypts and decrypts file contents with a derived key."""

    enc_key: bytes
    mac_key: bytes

    @classmethod
    def from_passphrase(
        cls,
        passphrase: str,
        salt_b64: str,
        *,
        n: int = SCRYPT_N,
        r: int = SCRYPT_R,
        p: int = SCRYPT_P,
    ) -> FileCipher:
        """Derive the keys. CPU heavy, run in an executor."""
        if not passphrase:
            raise ValueError("empty passphrase")
        salt = base64.b64decode(salt_b64)
        material = hashlib.scrypt(
            passphrase.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=128 * 1024 * 1024,
            dklen=64,
        )
        return cls(material[:32], material[32:])

    def mac(self, path: str, data: bytes) -> str:
        """Keyed fingerprint of path + plaintext."""
        digest = hmac.new(self.mac_key, path.encode("utf-8") + b"\x00" + data, "sha256")
        return digest.hexdigest()

    def encrypt(self, path: str, data: bytes) -> bytes:
        """Encrypt data for the given repository path (ASCII armored)."""
        nonce = os.urandom(NONCE_LEN)
        ciphertext = AESGCM(self.enc_key).encrypt(nonce, data, path.encode("utf-8"))
        return armor(path, MAGIC + nonce + ciphertext)

    def decrypt(self, path: str, blob: bytes) -> bytes:
        """Decrypt a blob created by encrypt for the same path."""
        blob = dearmor(blob)
        if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + NONCE_LEN + 16:
            raise DecryptionError("not a bastion encrypted blob")
        nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
        ciphertext = blob[len(MAGIC) + NONCE_LEN :]
        try:
            return AESGCM(self.enc_key).decrypt(nonce, ciphertext, path.encode("utf-8"))
        except InvalidTag as err:
            raise DecryptionError("wrong passphrase or modified file") from err


def kdf_params() -> dict[str, int]:
    """KDF parameters recorded in the repository manifest."""
    return {"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P}


def armor(path: str, payload: bytes) -> bytes:
    """Wrap the binary payload in a readable text block."""
    encoded = base64.b64encode(payload).decode()
    lines = [encoded[i : i + 76] for i in range(0, len(encoded), 76)]
    safe_path = path.replace("\n", " ")
    header = f"Version: {FORMAT_VERSION}\nPath: {safe_path}\n\n".encode()
    return ARMOR_BEGIN + b"\n" + header + "\n".join(lines).encode() + b"\n" + ARMOR_END + b"\n"


def dearmor(blob: bytes) -> bytes:
    """Return the binary payload of an armored or raw (version 1) blob."""
    if not blob.startswith(ARMOR_BEGIN):
        return blob
    body = blob[len(ARMOR_BEGIN) : blob.find(ARMOR_END)] if ARMOR_END in blob else blob[len(ARMOR_BEGIN) :]
    text = body.decode("ascii", "replace")
    _, _, data = text.partition("\n\n")
    try:
        return base64.b64decode("".join(data.split()), validate=True)
    except (binascii.Error, ValueError) as err:
        raise DecryptionError("damaged encrypted file") from err
