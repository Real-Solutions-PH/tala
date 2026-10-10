"""Biometric unlock with WebAuthn (spec section 3): the owner's platform authenticator (Face ID, Touch ID,
Android fingerprint) with user verification required.

- rp_id is the request host without its port. Browsers refuse WebAuthn on a bare IP, so an IP host gets
  400 `lock.biometricNeedsDomain` and the PIN stays the working path on the LAN. `localhost` is allowed.
- Challenges live here in memory for at most CHALLENGE_TTL seconds, bound to one profile and one purpose,
  and are consumed by the first verify that presents them.
- Credentials are stored as a JSON list in owner_lock.webauthn: [{id, public_key, sign_count, created}].
- A successful login creates the session through the same path as PIN unlock (deps.start_session).
"""
import base64
import ipaddress
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Annotated, Any

import webauthn as wa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from kapiling.auth import lock
from kapiling.auth.deps import Actor, require_owner, require_unlocked, start_session
from kapiling.db import get_con

__all__ = ["InvalidAuthenticationResponse", "InvalidRegistrationResponse", "has_biometric", "router"]

router = APIRouter(prefix="/api/webauthn")
Con = Annotated[sqlite3.Connection, Depends(get_con)]
Unlocked = Annotated[Actor, Depends(require_unlocked)]

RP_NAME = "Kapiling"
CHALLENGE_TTL = 120.0  # seconds; the browser prompt times out at the same moment
MAX_CHALLENGES = 256
FAILED = "settings.biometricFailed"

_challenges: dict[str, tuple[str, int, float]] = {}  # b64url challenge -> (purpose, profile_id, expires_at)
_mu = threading.Lock()


def _now() -> float:
    """Injectable clock (tests monkeypatch it)."""
    return time.monotonic()


def _verify(kind: str, **kwargs: Any) -> Any:
    """The one seam to py_webauthn's verifiers (tests replace this function)."""
    if kind == "registration":
        return wa.verify_registration_response(**kwargs)
    return wa.verify_authentication_response(**kwargs)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# --- host rules ----------------------------------------------------------------------

def _host(request: Request) -> str:
    """The Host header without its port ('[::1]:80' -> '::1')."""
    raw = (request.headers.get("host") or request.url.hostname or "").strip().lower()
    if raw.startswith("["):
        return raw[1:raw.index("]")] if "]" in raw else raw[1:]
    return raw.rsplit(":", 1)[0] if raw.count(":") == 1 else raw


def _rp_id(request: Request) -> str:
    host = _host(request)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host:
            return host
    raise HTTPException(400, "lock.biometricNeedsDomain")


def _origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.headers.get('host') or request.url.netloc}"


# --- challenges --------------------------------------------------------------------------

def _issue(purpose: str, pid: int, challenge: bytes) -> None:
    now = _now()
    with _mu:
        for k in [k for k, (_, _, exp) in _challenges.items() if exp <= now]:
            del _challenges[k]
        while len(_challenges) >= MAX_CHALLENGES:  # login/options is public: bound the memory a flood can take
            del _challenges[next(iter(_challenges))]
        _challenges[_b64(challenge)] = (purpose, pid, now + CHALLENGE_TTL)


def _consume(purpose: str, pid: int, credential: dict) -> bytes:
    """Pop the challenge named in the credential's clientDataJSON; it must be live and issued for this
    purpose and profile. Single use: it is gone whether or not the rest of the check passes."""
    try:
        client_data = json.loads(_unb64(credential["response"]["clientDataJSON"]))
        key = client_data["challenge"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, FAILED) from None
    with _mu:
        entry = _challenges.pop(key, None) if isinstance(key, str) else None
    if entry is None or entry[0] != purpose or entry[1] != pid or entry[2] <= _now():
        raise HTTPException(400, FAILED)
    return _unb64(key)


# --- credential storage ------------------------------------------------------------------------

def _creds(con: sqlite3.Connection, pid: int) -> list[dict]:
    row = con.execute("select webauthn from owner_lock where profile_id=?", (pid,)).fetchone()
    if row is None or not row["webauthn"]:
        return []
    try:
        creds = json.loads(row["webauthn"])
    except ValueError:
        return []
    return creds if isinstance(creds, list) else []


def _save(con: sqlite3.Connection, pid: int, creds: list[dict]) -> None:
    con.execute("update owner_lock set webauthn=? where profile_id=?", (json.dumps(creds), pid))
    con.commit()


def has_biometric(con: sqlite3.Connection, pid: int) -> bool:
    return bool(_creds(con, pid))


def _owner_actor(con: sqlite3.Connection, pid: int) -> Actor:
    p = con.execute("select nickname, full_name from profiles where id=?", (pid,)).fetchone()
    return {"profile_id": pid, "name": p["nickname"] or p["full_name"], "role": "owner"}


def _platform_only(credential: dict) -> None:
    # The options ask for a platform authenticator; refuse a client that answered with a roaming key.
    if credential.get("authenticatorAttachment", "platform") != "platform":
        raise HTTPException(400, FAILED)


# --- registration (owner, unlocked) -----------------------------------------------------------------

@router.post("/register/options")
def register_options(request: Request, con: Con, actor: Unlocked):
    require_owner(con, actor, "enrol_biometric")
    pid = actor["profile_id"]
    rp_id = _rp_id(request)
    opts = wa.generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_id=f"kapiling-{pid}".encode(), user_name=actor["name"],
        user_display_name=actor["name"], timeout=int(CHALLENGE_TTL * 1000),
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.DISCOURAGED,
            user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=_unb64(c["id"])) for c in _creds(con, pid)])
    _issue("register", pid, opts.challenge)
    return Response(wa.options_to_json(opts), media_type="application/json")


class RegisterBody(BaseModel):
    credential: dict


@router.post("/register/verify", status_code=204)
def register_verify(body: RegisterBody, request: Request, con: Con, actor: Unlocked):
    require_owner(con, actor, "enrol_biometric")
    pid = actor["profile_id"]
    rp_id = _rp_id(request)
    _platform_only(body.credential)
    challenge = _consume("register", pid, body.credential)
    try:
        v = _verify("registration", credential=body.credential, expected_challenge=challenge, expected_rp_id=rp_id,
                    expected_origin=_origin(request), require_user_verification=True)
    except (InvalidRegistrationResponse, ValueError, KeyError, TypeError):
        lock.log_access(con, pid, actor, "enrol_biometric_failed")
        raise HTTPException(400, FAILED) from None
    creds = [c for c in _creds(con, pid) if c["id"] != _b64(v.credential_id)]
    creds.append({"id": _b64(v.credential_id), "public_key": _b64(v.credential_public_key),
                  "sign_count": int(v.sign_count), "created": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    _save(con, pid, creds)
    lock.log_access(con, pid, actor, "enrol_biometric")


@router.delete("/credentials", status_code=204)
def remove_credentials(con: Con, actor: Unlocked):
    require_owner(con, actor, "remove_biometric")
    _save(con, actor["profile_id"], [])
    lock.log_access(con, actor["profile_id"], actor, "remove_biometric")


# --- login (public, from the lock screen) -------------------------------------------------------------

class LoginOptionsBody(BaseModel):
    profile_id: int


@router.post("/login/options")
def login_options(body: LoginOptionsBody, request: Request, con: Con):
    rp_id = _rp_id(request)
    creds = _creds(con, body.profile_id)
    if not creds:
        raise HTTPException(404, "settings.biometricNotSet")
    opts = wa.generate_authentication_options(
        rp_id=rp_id, timeout=int(CHALLENGE_TTL * 1000), user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[PublicKeyCredentialDescriptor(id=_unb64(c["id"])) for c in creds])
    _issue("login", body.profile_id, opts.challenge)
    return Response(wa.options_to_json(opts), media_type="application/json")


class LoginVerifyBody(BaseModel):
    profile_id: int
    credential: dict


@router.post("/login/verify", status_code=204)
def login_verify(body: LoginVerifyBody, request: Request, response: Response, con: Con):
    pid = body.profile_id
    rp_id = _rp_id(request)
    _platform_only(body.credential)
    challenge = _consume("login", pid, body.credential)
    creds = _creds(con, pid)
    match = next((c for c in creds if c["id"] == body.credential.get("id")), None)
    if match is None:
        lock.log_access(con, pid, lock.UNKNOWN, "unlock_failed", "biometric")
        raise HTTPException(400, FAILED)
    try:
        v = _verify("authentication", credential=body.credential, expected_challenge=challenge, expected_rp_id=rp_id,
                    expected_origin=_origin(request), credential_public_key=_unb64(match["public_key"]),
                    credential_current_sign_count=int(match["sign_count"]), require_user_verification=True)
    except (InvalidAuthenticationResponse, ValueError, KeyError, TypeError):
        v = None
    # The library checks the counter too; checked again here so a regression can never open a session.
    stored, new = int(match["sign_count"]), int(v.new_sign_count) if v else -1
    if v is None or ((stored or new) and new <= stored):
        lock.log_access(con, pid, lock.UNKNOWN, "unlock_failed", "biometric")
        raise HTTPException(400, FAILED)
    match["sign_count"] = new
    _save(con, pid, creds)
    actor = _owner_actor(con, pid)
    start_session(request, response, actor)
    lock.log_access(con, pid, actor, "unlock", "biometric")
