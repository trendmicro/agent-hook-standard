"""Cryptographic utilities for Agent Hook Specification.

Includes:
- Ed25519 key generation, signing, and verification.
- Canonical JSON serialization (RFC 8785 compatible).
- Content-Identity SHA-256 fingerprinting.
- Wire header signature creation and verification.
- Tamper-evident audit ledger hash chaining.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize Python object to RFC 8785 compatible canonical JSON bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_str(obj: Any) -> str:
    """Serialize Python object to RFC 8785 compatible canonical JSON string."""
    return canonical_json_bytes(obj).decode("utf-8")


def compute_content_identity(payload: Dict[str, Any]) -> str:
    """Compute SHA-256 fingerprint for event_payload: sha256:<64_hex_chars>."""
    canonical_bytes = canonical_json_bytes(payload)
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest}"


class Ed25519KeyPair:
    """Wraps an Ed25519 key pair for Agent / Receiver signatures."""

    def __init__(
        self,
        private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        public_key: Optional[ed25519.Ed25519PublicKey] = None,
        key_id: str = "key-default",
    ):
        if private_key:
            self._private_key = private_key
            self._public_key = private_key.public_key()
        elif public_key:
            self._private_key = None
            self._public_key = public_key
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
        self.key_id = key_id

    @property
    def public_bytes_raw(self) -> bytes:
        return self._public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )

    @property
    def public_hex(self) -> str:
        return self.public_bytes_raw.hex()

    @property
    def public_base64(self) -> str:
        return base64.b64encode(self.public_bytes_raw).decode("utf-8")

    def sign_bytes(self, data: bytes) -> bytes:
        if not self._private_key:
            raise ValueError("Cannot sign without private key")
        return self._private_key.sign(data)

    def sign_string(self, text: str) -> str:
        """Sign string and return base64 encoded signature."""
        sig = self.sign_bytes(text.encode("utf-8"))
        return base64.b64encode(sig).decode("utf-8")

    def verify_bytes(self, signature: bytes, data: bytes) -> bool:
        try:
            self._public_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False

    def verify_string(self, base64_sig: str, text: str) -> bool:
        try:
            raw_sig = base64.b64decode(base64_sig)
            return self.verify_bytes(raw_sig, text.encode("utf-8"))
        except Exception:
            return False

    @classmethod
    def from_public_raw(cls, public_bytes: bytes, key_id: str = "key-imported") -> Ed25519KeyPair:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
        return cls(public_key=pub, key_id=key_id)

    @classmethod
    def from_public_hex(cls, hex_str: str, key_id: str = "key-imported") -> Ed25519KeyPair:
        return cls.from_public_raw(bytes.fromhex(hex_str), key_id=key_id)


def build_signature_payload(hook_id: str, timestamp: int, body_str: str) -> str:
    """Build canonical payload for wire header signature: {Hook-Id}.{Hook-Timestamp}.{Body}."""
    return f"{hook_id}.{timestamp}.{body_str}"


def sign_wire_request(
    keypair: Ed25519KeyPair,
    hook_id: str,
    timestamp: int,
    body_str: str,
) -> str:
    """Create Hook-Signature value: v1,ed25519=<base64_signature>."""
    signing_input = build_signature_payload(hook_id, timestamp, body_str)
    sig_b64 = keypair.sign_string(signing_input)
    return f"v1,ed25519={sig_b64}"


def verify_wire_signature(
    public_keypair: Ed25519KeyPair,
    hook_id: str,
    timestamp: int,
    body_str: str,
    hook_signature_header: str,
) -> bool:
    """Verify Hook-Signature header value."""
    if not hook_signature_header.startswith("v1,ed25519="):
        return False
    sig_b64 = hook_signature_header[len("v1,ed25519="):]
    signing_input = build_signature_payload(hook_id, timestamp, body_str)
    return public_keypair.verify_string(sig_b64, signing_input)


def compute_audit_record_hash(record_dict: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of an audit record for cryptographic ledger chaining."""
    canonical_bytes = canonical_json_bytes(record_dict)
    return f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"


def build_approval_grant_payload(
    approval_id: str,
    decision: str,
    content_identity_echo: str,
    approver_subject: str,
    timestamp: str,
) -> str:
    """Canonical signing input for approval grant token."""
    return f"{approval_id}.{decision}.{content_identity_echo}.{approver_subject}.{timestamp}"


def sign_approval_grant(
    keypair: Ed25519KeyPair,
    approval_id: str,
    decision: str,
    content_identity_echo: str,
    approver_subject: str,
    timestamp: str,
) -> str:
    """Create approval_grant_token: v1,ed25519=<base64_signature>."""
    signing_input = build_approval_grant_payload(
        approval_id=approval_id,
        decision=decision,
        content_identity_echo=content_identity_echo,
        approver_subject=approver_subject,
        timestamp=timestamp,
    )
    sig_b64 = keypair.sign_string(signing_input)
    return f"v1,ed25519={sig_b64}"


def verify_approval_grant(
    public_keypair: Ed25519KeyPair,
    approval_id: str,
    decision: str,
    content_identity_echo: str,
    approver_subject: str,
    timestamp: str,
    grant_token: str,
) -> bool:
    """Verify approval_grant_token signature."""
    if not grant_token.startswith("v1,ed25519="):
        return False
    sig_b64 = grant_token[len("v1,ed25519="):]
    signing_input = build_approval_grant_payload(
        approval_id=approval_id,
        decision=decision,
        content_identity_echo=content_identity_echo,
        approver_subject=approver_subject,
        timestamp=timestamp,
    )
    return public_keypair.verify_string(sig_b64, signing_input)
