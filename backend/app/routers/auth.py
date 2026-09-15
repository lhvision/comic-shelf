"""Authentication, guest pass claiming, session cookies, and curator pass administration router."""
from __future__ import annotations

import secrets
from fastapi import APIRouter, HTTPException, Request, Response

from ..abuse import (
    clear_ip_login_failures,
    clear_pin_failures,
    is_ip_login_locked,
    is_pin_locked,
    record_ip_login_failure_and_check_lock,
    record_pin_failure_and_check_lock,
)
from ..auth import (
    clear_auth_cookie,
    clear_device_cookie,
    extract_device_token,
    extract_token,
    get_client_ip,
    get_user_context,
    is_auth_required,
    is_request_secure,
    require_curator,
    set_auth_cookie,
    set_device_cookie,
)
from ..config import AUTH_SECRET
from ..db import (
    claim_guest_pass,
    create_guest_pass,
    delete_guest_device,
    delete_guest_pass,
    get_device_by_token,
    get_guest_pass_by_token,
    list_guest_passes,
    register_guest_device,
    touch_device_active,
    update_guest_pass,
    verify_guest_pass_pin,
)
from ..models import (
    AuthStatusResponse,
    ClaimGuestPassRequest,
    CreateGuestPassRequest,
    GuestPassItem,
    LoginRequest,
    LoginResponse,
    UpdateGuestPassRequest,
)

router = APIRouter(tags=["auth"])


@router.get("/api/auth/status", response_model=AuthStatusResponse)
def auth_status(request: Request, response: Response) -> AuthStatusResponse:
    """Returns the current authentication and permission status of the calling client."""
    auth_req = is_auth_required()
    user_id, username, role = get_user_context(request)
    curator = role == "admin"
    guest = role == "guest"
    authed = curator or guest
    if authed and hasattr(request.state, "new_device_token"):
        is_sec = is_request_secure(request)
        set_device_cookie(response, request.state.new_device_token, secure=is_sec)

    requires_claim = False
    requires_pin = False
    token = extract_token(request)
    p_item = None
    if not authed and token:
        p_item = get_guest_pass_by_token(token)
        if p_item and p_item["is_active"] and not p_item["is_expired"]:
            if not p_item["is_claimed"]:
                requires_claim = True
            else:
                requires_pin = True

    return AuthStatusResponse(
        auth_required=auth_req,
        authenticated=authed,
        can_write=curator,
        role=role if authed else "unauthorized",
        username=username if authed else (p_item["username"] if p_item and (requires_claim or requires_pin) else ""),
        user_id=user_id if authed else (f"guest:{p_item['id']}" if p_item and (requires_claim or requires_pin) else ""),
        is_claimed=not requires_claim,
        requires_pin=requires_pin,
        requires_claim=requires_claim,
    )


@router.post("/api/auth/login", response_model=LoginResponse)
def auth_login(req: LoginRequest, request: Request, response: Response) -> LoginResponse:
    """Authenticates curator secret or guest pass token with PIN and device binding."""
    if not is_auth_required():
        return LoginResponse(ok=True, token="", role="admin", username="馆长", user_id="curator")

    ip = get_client_ip(request)
    if is_ip_login_locked(ip):
        raise HTTPException(status_code=429, detail="口令尝试过于频繁，该网络地址已临时锁定 5 分钟，请稍后再试")

    is_sec = is_request_secure(request)
    secret = req.secret.strip()
    if AUTH_SECRET and secrets.compare_digest(secret, AUTH_SECRET):
        clear_ip_login_failures(ip)
        set_auth_cookie(response, AUTH_SECRET, secure=is_sec)
        clear_device_cookie(response, secure=is_sec)  # Clean up any lingering guest device session
        return LoginResponse(ok=True, token=AUTH_SECRET, role="admin", username="馆长", user_id="curator")

    pass_item = get_guest_pass_by_token(secret)
    if pass_item is not None:
        if not pass_item["is_active"]:
            record_ip_login_failure_and_check_lock(ip)
            raise HTTPException(status_code=401, detail="该访客通行证已被停用")
        if pass_item["is_expired"]:
            record_ip_login_failure_and_check_lock(ip)
            raise HTTPException(status_code=401, detail="通行证已过期，请联系馆长续期")

        ua = request.headers.get("user-agent", "")

        # Case A: Unclaimed pass -> requires setting PIN
        if not pass_item["is_claimed"]:
            if not req.pin or not req.pin.strip():
                return LoginResponse(
                    ok=False,
                    token=pass_item["token"],
                    role="guest",
                    username=pass_item["username"],
                    user_id=f"guest:{pass_item['id']}",
                    is_claimed=False,
                    requires_claim=True,
                )
            try:
                claimed = claim_guest_pass(pass_item["id"], req.pin, req.username)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

            try:
                dev = register_guest_device(claimed["id"], user_agent=ua, ip=ip)
            except ValueError as exc:
                msg = str(exc)
                if "频繁" in msg or "安全保护锁定" in msg:
                    raise HTTPException(status_code=429, detail=msg)
                raise HTTPException(status_code=400, detail=msg)

            clear_ip_login_failures(ip)
            set_auth_cookie(response, claimed["token"], secure=is_sec)
            set_device_cookie(response, dev["device_token"], secure=is_sec)
            return LoginResponse(
                ok=True,
                token=claimed["token"],
                role="guest",
                username=claimed["username"],
                user_id=f"guest:{claimed['id']}",
                device_token=dev["device_token"],
                is_claimed=True,
            )

        # Case B: Claimed pass -> check device token or require PIN
        dev = None
        existing_dev_token = extract_device_token(request)
        if existing_dev_token:
            existing_dev = get_device_by_token(existing_dev_token)
            if existing_dev and existing_dev.get("pass_id") == pass_item["id"]:
                dev = existing_dev
                touch_device_active(dev["id"], ip)

        if dev is not None:
            clear_ip_login_failures(ip)
            set_auth_cookie(response, pass_item["token"], secure=is_sec)
            set_device_cookie(response, dev["device_token"], secure=is_sec)
            return LoginResponse(
                ok=True,
                token=pass_item["token"],
                role="guest",
                username=pass_item["username"],
                user_id=f"guest:{pass_item['id']}",
                device_token=dev["device_token"],
                is_claimed=True,
            )

        if not req.pin or not req.pin.strip():
            return LoginResponse(
                ok=False,
                token=pass_item["token"],
                role="guest",
                username=pass_item["username"],
                user_id=f"guest:{pass_item['id']}",
                is_claimed=True,
                requires_pin=True,
            )

        locked, lock_reason = is_pin_locked(pass_item["id"], ip)
        if locked:
            raise HTTPException(status_code=429, detail=lock_reason)

        if not verify_guest_pass_pin(pass_item["id"], req.pin.strip()):
            is_now_locked, failure_reason = record_pin_failure_and_check_lock(pass_item["id"], ip)
            if is_now_locked:
                raise HTTPException(status_code=429, detail=failure_reason)
            raise HTTPException(status_code=401, detail="PIN 码错误，请重新输入")

        clear_pin_failures(pass_item["id"], ip)
        clear_ip_login_failures(ip)

        try:
            dev = register_guest_device(pass_item["id"], user_agent=ua, ip=ip)
        except ValueError as exc:
            msg = str(exc)
            if "频繁" in msg or "安全保护锁定" in msg:
                raise HTTPException(status_code=429, detail=msg)
            raise HTTPException(status_code=400, detail=msg)

        set_auth_cookie(response, pass_item["token"], secure=is_sec)
        set_device_cookie(response, dev["device_token"], secure=is_sec)
        return LoginResponse(
            ok=True,
            token=pass_item["token"],
            role="guest",
            username=pass_item["username"],
            user_id=f"guest:{pass_item['id']}",
            device_token=dev["device_token"],
            is_claimed=True,
        )

    if record_ip_login_failure_and_check_lock(ip):
        raise HTTPException(status_code=429, detail="口令尝试过于频繁，该网络地址已临时锁定 5 分钟，请稍后再试")
    raise HTTPException(status_code=401, detail="通行口令错误，请重试")


@router.post("/api/auth/claim", response_model=LoginResponse)
def auth_claim(req: ClaimGuestPassRequest, request: Request, response: Response) -> LoginResponse:
    """Claims an initial unactivated guest pass by establishing user PIN and alias."""
    return auth_login(LoginRequest(secret=req.token, pin=req.pin, username=req.username), request, response)


@router.post("/api/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    """Clears client session cookies and revokes active device session token."""
    dev_token = extract_device_token(request)
    if dev_token:
        dev = get_device_by_token(dev_token)
        if dev:
            delete_guest_device(dev["id"])
    is_sec = is_request_secure(request)
    clear_auth_cookie(response, secure=is_sec)
    clear_device_cookie(response, secure=is_sec)
    return {"ok": True}


# ----------------------------------------------------------------------
# 馆长访客通行证管理（Curator Passes Management）
# ----------------------------------------------------------------------

@router.get("/api/curator/passes", response_model=list[GuestPassItem])
def curator_list_passes(request: Request) -> list[GuestPassItem]:
    """Lists all active and expired guest passes for curator management."""
    require_curator(request)
    return [GuestPassItem(**p) for p in list_guest_passes()]


@router.post("/api/curator/passes", response_model=GuestPassItem)
def curator_create_pass(req: CreateGuestPassRequest, request: Request) -> GuestPassItem:
    """Creates a new guest pass with customizable token and device quota."""
    require_curator(request)
    try:
        p = create_guest_pass(
            username=req.username,
            expires_days=req.expires_days,
            custom_token=req.custom_token,
            pin=req.pin,
            max_devices=req.max_devices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return GuestPassItem(**p)


@router.patch("/api/curator/passes/{pass_id}", response_model=GuestPassItem)
def curator_update_pass(pass_id: int, req: UpdateGuestPassRequest, request: Request) -> GuestPassItem:
    """Updates metadata, status, PIN or expiration of an existing guest pass."""
    require_curator(request)
    try:
        p = update_guest_pass(
            pass_id=pass_id,
            username=req.username,
            is_active=req.is_active,
            extend_days=req.extend_days,
            reset_token=req.reset_token,
            reset_pin=req.reset_pin,
            custom_pin=req.custom_pin,
            expires_days=req.expires_days,
            max_devices=req.max_devices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if p is None:
        raise HTTPException(status_code=404, detail="未找到该访客通行证")
    if req.reset_pin or req.custom_pin:
        clear_pin_failures(pass_id)
    return GuestPassItem(**p)


@router.delete("/api/curator/passes/{pass_id}")
def curator_delete_pass(pass_id: int, request: Request) -> dict[str, bool]:
    """Permanently revokes and deletes a guest pass and all its associated device tokens."""
    require_curator(request)
    ok = delete_guest_pass(pass_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该访客通行证")
    return {"ok": True}


@router.delete("/api/curator/passes/{pass_id}/devices/{device_id}")
def curator_delete_pass_device(pass_id: int, device_id: int, request: Request) -> dict[str, bool]:
    """Forcefully disconnects and evicts a specific device under a guest pass."""
    require_curator(request)
    ok = delete_guest_device(device_id, pass_id=pass_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该设备或已被移除")
    return {"ok": True}
