from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import random
import re
import threading
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

from ..config import (
    COVER_COUNT,
    DATA_DIR,
    PICA_API_URL,
    PICA_CHANNEL,
    PICA_EMAIL,
    PICA_PASSWORD,
    PICA_PROXY,
)
from ..gate import download_gate
from ..models import Chapter, ComicMeta, DiscoveryItem, FetchedComic, PageRecord, RemotePage
from ..formatting import format_count
from .base import ComicProvider

logger = logging.getLogger(__name__)

PICA_API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"
PICA_SECRET_KEY = "~d}$Q7$eIni=V)9\\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"
PICA_APP_VERSION = "2.2.1.3.3.4"
PICA_APP_BUILD_VERSION = "45"
PICA_APP_PLATFORM = "android"

PICA_STORAGE_FALLBACKS = [
    "storage1.picacomic.com",
    "storage1.bwaa.co",
    "storage.wikawika.xyz",
    "storage2.bwaa.co",
    "storage3.bwaa.co",
]


def calc_signature(path: str, nonce: str, time_str: str, method: str) -> str:
    """Calculates the HMAC-SHA256 signature required by PicAcg mobile REST API.
    Ref: https://github.com/wgh136/PicaComic (PicaComic by wgh136)

    The path should be the endpoint relative to the base URL, including query strings if present,
    lowercased along with the timestamp, nonce, method, and the mobile API key.
    """
    clean_path = path.lstrip("/")
    raw = f"{clean_path}{time_str}{nonce}{method.upper()}{PICA_API_KEY}".lower()
    return hmac.new(
        PICA_SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def format_date(val: Any) -> str:
    """Extract YYYY-MM-DD date from ISO 8601 or timestamp strings."""
    if not val:
        return ""
    s = str(val).strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else s


PICA_ALLOWED_CDN_SUFFIXES = (
    ".bwaa.co",
    ".wikawika.xyz",
    ".picacomic.com",
    ".storage.live.com",
)

PICA_EXTRA_CDN_HOSTS = [
    h.strip().lower() for h in os.getenv("PICA_EXTRA_CDN_HOSTS", "").split(",") if h.strip()
]

# Polite human-like rate limiting / pacing configuration (in milliseconds)
PICA_DOWNLOAD_PACING_MS = float(os.getenv("PICA_DOWNLOAD_PACING_MS", "250"))
PICA_API_PACING_MS = float(os.getenv("PICA_API_PACING_MS", "150"))


def _apply_pacing(base_ms: float) -> None:
    """Apply a polite human-like pacing delay with +/-20% random jitter."""
    if base_ms <= 0:
        return
    jitter = random.uniform(0.8, 1.2)
    time.sleep((base_ms / 1000.0) * jitter)

_PROXY_CRED_RE = re.compile(r"://([^:@\s]+):([^@\s]+)@")


def sanitize_proxy_url(text: str) -> str:
    """Mask credentials (username:password) in proxy URLs or error messages."""
    return _PROXY_CRED_RE.sub(r"://\1:***@", text)


def is_valid_image(data: bytes) -> bool:
    """Validate that raw bytes start with valid image magic bytes.

    Supports JPEG, PNG, WebP, GIF, and AVIF.
    """
    if len(data) < 16:
        return False
    # JPEG: FF D8 FF
    if data.startswith(b"\xff\xd8\xff"):
        return True
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    # WebP: RIFF....WEBP
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    # GIF: GIF87a / GIF89a
    if data.startswith((b"GIF87a", b"GIF89a")):
        return True
    # AVIF: ....ftypavif / avis
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return True
    return False


def _validate_download_host(host: str) -> None:
    """Validate target host for SSRF prevention.

    Rejects localhost, loopback, private networks, direct IP accesses, well-known pseudo-domain
    rebinding services (*.nip.io, *.sslip.io, localtest.me), and unauthorized non-CDN hosts.
    """
    cleaned_host = (host or "").strip().lower()
    if not cleaned_host or cleaned_host in ("localhost", "localtest.me"):
        raise ValueError(f"禁止访问敏感或未知的画页下载目标: {host}")

    # Check if host is a literal IP address
    try:
        ip = ipaddress.ip_address(cleaned_host)
        is_ip = True
    except ValueError:
        is_ip = False

    if is_ip:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"禁止下载私有或保留网络地址图片: {host}")
        raise ValueError(f"禁止使用直接 IP 地址访问画页 CDN: {host}")

    # Block pseudo-DNS rebinding and internal suffixes
    if cleaned_host.endswith(
        (".local", ".internal", ".lan", ".home", ".corp", ".onion", ".nip.io", ".sslip.io")
    ):
        raise ValueError(f"禁止下载内部网络或重绑定域名图片: {host}")

    # Validate against authorized PicAcg CDN domain suffixes, fallback storage hosts, or custom CDN hosts
    is_authorized_cdn = (
        any(
            cleaned_host == suffix.lstrip(".") or cleaned_host.endswith(suffix)
            for suffix in PICA_ALLOWED_CDN_SUFFIXES
        )
        or (cleaned_host in PICA_STORAGE_FALLBACKS)
        or (cleaned_host in PICA_EXTRA_CDN_HOSTS)
    )

    if not is_authorized_cdn:
        raise ValueError(f"非法的哔咔画页 CDN 域名: {host}")


class PicacgProvider(ComicProvider):
    """哔咔漫画 (PicAcg) 数据源 Provider.

    采用官方移动端 HMAC-SHA256 签名 REST 协议获取元数据与分卷章节，
    支持多分流自动轮换降级下载画页，原生兼容 PicaWeb 网页端及镜像分享链接。
    """

    key = "picacg"
    label = "哔咔漫画 (PicACG)"
    short_label = "哔咔"
    id_pattern = r"(?:(?:https?://[^/]+/comic/)|(?:[Pp][Ii][Cc][Aa]:?))?([0-9a-fA-F]{24})"
    example = "5ebe89bf63918511c2c362a7 或 网页链接"

    # Thread-local session pool for Keep-Alive connection reuse across concurrent downloads
    _tls = threading.local()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_file = DATA_DIR / "picacg_session.json"

    def _session(self) -> curl_requests.Session:
        session = getattr(self._tls, "session", None)
        if session is None:
            session = curl_requests.Session(impersonate="chrome")
            self._tls.session = session
        return session

    # ------------------------------------------------------------------
    # ID normalization & URL parsing
    # ------------------------------------------------------------------
    def normalize_id(self, raw: str) -> str:
        """Extract canonical 24-character hexadecimal ObjectId from user input,
        prefixed strings (e.g. PICA:xxx), or web links (picawang.com, manhuabika.com, etc.).
        """
        cleaned = raw.strip()
        m = re.search(r"(?:(?:comic|comics)/|[Pp][Ii][Cc][Aa]:?|^|\b)([0-9a-fA-F]{24})\b", cleaned)
        if m is None:
            raise ValueError(
                "哔咔车号格式不正确，支持24位Hex ID或网页分享链接（如 https://picawang.com/comic/5ebe89bf63918511c2c362a7）"
            )
        return m.group(1).lower()

    # ------------------------------------------------------------------
    # Headers & Authentication
    # ------------------------------------------------------------------
    def _create_headers(
        self,
        path: str,
        method: str = "GET",
        token: str | None = None,
    ) -> dict[str, str]:
        time_str = str(int(time.time()))
        nonce = uuid.uuid4().hex
        sig = calc_signature(path, nonce, time_str, method)
        headers = {
            "api-key": PICA_API_KEY,
            "accept": "application/vnd.picacomic.com.v1+json",
            "app-channel": PICA_CHANNEL or "2",
            "time": time_str,
            "nonce": nonce,
            "signature": sig,
            "app-version": PICA_APP_VERSION,
            "app-uuid": "defaultUuid",
            "app-platform": PICA_APP_PLATFORM,
            "app-build-version": PICA_APP_BUILD_VERSION,
            "User-Agent": "okhttp/3.8.1",
            "image-quality": "original",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if token:
            headers["authorization"] = token
        return headers

    def _load_cached_token(self) -> str | None:
        data = self.load_secure_session(self._session_file)
        if not data:
            return None
        token = data.get("token")
        cached_email = data.get("email")
        configured_email = (PICA_EMAIL or "").strip()
        if configured_email and cached_email != configured_email:
            return None
        # Token valid for 7 days (604800 seconds)
        try:
            ts = float(data.get("time") or 0)
        except (TypeError, ValueError):
            return None
        if token and time.time() - ts < 7 * 24 * 3600:
            return str(token)
        return None

    def _save_token(self, token: str, email: str) -> None:
        self.save_secure_session(
            self._session_file,
            {
                "token": token,
                "email": email,
                "time": time.time(),
            },
        )

    def login(self, email: str | None = None, password: str | None = None) -> str:
        """Authenticates with PicAcg and returns a fresh JWT authorization token."""
        act_email = (email or PICA_EMAIL).strip()
        act_pwd = (password or PICA_PASSWORD).strip()
        if not act_email or not act_pwd:
            raise ValueError(
                "未配置哔咔账号，请在环境变量配置 PICA_EMAIL 与 PICA_PASSWORD，或在后端 .env 中设置"
            )

        endpoint = "auth/sign-in"
        url = f"{PICA_API_URL.rstrip('/')}/{endpoint}"
        headers = self._create_headers(endpoint, method="POST")

        proxies = {"http": PICA_PROXY, "https": PICA_PROXY} if PICA_PROXY else None
        session = self._session()

        try:
            resp = session.post(
                url,
                json={"email": act_email, "password": act_pwd},
                headers=headers,
                proxies=proxies,
                timeout=15,
            )
        except Exception as exc:
            safe_err = sanitize_proxy_url(str(exc))
            raise RuntimeError(f"连接哔咔登录服务器失败: {safe_err}。若在国内网络请确认 PICA_PROXY 是否已开启") from exc

        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                pass
            raise RuntimeError(f"哔咔登录失败 ({resp.status_code}): {sanitize_proxy_url(err_msg)}")

        body = resp.json()
        token = body.get("data", {}).get("token")
        if not token:
            raise RuntimeError(f"哔咔登录响应中缺少 token 字段: {body}")

        self._save_token(token, act_email)
        logger.info("哔咔账号登录成功并已更新本地 Session")
        return str(token)

    def ensure_token(self) -> str:
        """Returns a valid authentication token, logging in if necessary."""
        token = self._load_cached_token()
        if token:
            return token

        with self._lock:
            token = self._load_cached_token()
            if token:
                return token
            return self.login()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Sends an authenticated request to PicAcg REST API.
        Ref: https://github.com/wgh136/PicaComic (PicaComic by wgh136)
        """
        from urllib.parse import urlencode

        clean_endpoint = endpoint.lstrip("/")
        if params:
            query = urlencode(params)
            sep = "&" if "?" in clean_endpoint else "?"
            clean_endpoint = f"{clean_endpoint}{sep}{query}"

        token = self.ensure_token()
        headers = self._create_headers(clean_endpoint, method=method, token=token)
        url = f"{PICA_API_URL.rstrip('/')}/{clean_endpoint}"
        proxies = {"http": PICA_PROXY, "https": PICA_PROXY} if PICA_PROXY else None
        session = self._session()

        try:
            if method.upper() == "GET":
                resp = session.get(url, headers=headers, proxies=proxies, timeout=20)
            else:
                resp = session.post(url, json=json_data, headers=headers, proxies=proxies, timeout=20)
        except Exception as exc:
            safe_err = sanitize_proxy_url(str(exc))
            raise RuntimeError(f"请求哔咔 API 失败 ({clean_endpoint}): {safe_err}") from exc

        if resp.status_code == 401 and retry_auth:
            logger.warning("哔咔 Token 已过期，尝试重新登录...")
            with self._lock:
                current_cached = self._load_cached_token()
                # If another thread has already refreshed the token while we waited on the lock, skip re-login
                if not current_cached or current_cached == token:
                    self.login()
            return self._request(method, endpoint, params=params, json_data=json_data, retry_auth=False)

        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                pass
            raise RuntimeError(f"哔咔接口响应异常 ({resp.status_code}): {err_msg}")

        try:
            return resp.json()
        except Exception as exc:
            raise RuntimeError(f"解析哔咔响应 JSON 失败: {exc}, 原文: {resp.text[:200]}") from exc

    # ------------------------------------------------------------------
    # ComicProvider interface implementation
    # ------------------------------------------------------------------
    def fetch(
        self,
        raw_id: str,
        *,
        existing: FetchedComic | None = None,
    ) -> FetchedComic:
        """Fetches comic metadata and page URLs without downloading image bytes."""
        comic_id = self.normalize_id(raw_id)

        # 1. Fetch comic basic details
        detail_data = self._request("GET", f"comics/{comic_id}")
        comic_info = detail_data.get("data", {}).get("comic", {})
        if not comic_info:
            raise ValueError(f"未找到哔咔漫画或作品为空: {comic_id}")

        title = (comic_info.get("title") or f"PicAcg_{comic_id}").strip()
        author = (comic_info.get("author") or "").strip()
        authors = [author] if author else []
        chinese_team = (comic_info.get("chineseTeam") or "").strip()
        uploader = chinese_team or (comic_info.get("_creator", {}).get("name") if isinstance(comic_info.get("_creator"), dict) else None)

        raw_tags = comic_info.get("tags") or []
        raw_cats = comic_info.get("categories") or []
        tags = list(dict.fromkeys([t.strip() for t in (raw_tags + raw_cats) if t and t.strip()]))

        description = (comic_info.get("description") or "").strip()
        views = format_count(comic_info.get("viewsCount", comic_info.get("totalViews", "")))
        likes = format_count(comic_info.get("likesCount", comic_info.get("totalLikes", "")))
        published_at = format_date(comic_info.get("created_at") or "")
        updated_at = format_date(comic_info.get("updated_at") or comic_info.get("created_at") or "")

        # 2. Fetch all episode listings (with pagination)
        eps: list[dict[str, Any]] = []
        page = 1
        while True:
            eps_data = self._request("GET", f"comics/{comic_id}/eps", params={"page": page})
            eps_container = eps_data.get("data", {}).get("eps", {})
            docs = eps_container.get("docs", [])
            eps.extend(docs)
            total_pages = int(eps_container.get("pages", 1))
            if page >= total_pages or not docs or page >= 500:
                break
            page += 1

        # Sort episodes by natural order
        eps.sort(key=lambda x: int(x.get("order", 0)))

        # Fallback if no episodes returned (e.g. single-chapter legacy entry)
        if not eps:
            eps = [{"order": 1, "title": "第 1 話", "_id": comic_id}]

        existing_chapter_map = {
            c.id: c for c in (existing.meta.chapters if existing else [])
        }
        existing_pages_by_chap: dict[str, list[RemotePage]] = {}
        if existing:
            for p in existing.remote_pages:
                chap_id = p.chapter or "1"
                existing_pages_by_chap.setdefault(chap_id, []).append(p)

        chapters: list[Chapter] = []
        remote_pages: list[RemotePage] = []
        page_records: list[PageRecord] = []
        global_page_index = 1

        # 3. Fetch pages for each episode (reusing existing unchanged chapters)
        for ep_idx, ep in enumerate(eps, start=1):
            ep_order = int(ep.get("order", ep_idx))
            chap_id = str(ep_order)
            ep_title = (ep.get("title") or f"第 {ep_order} 話").strip()
            ep_start = global_page_index

            cached_pages = existing_pages_by_chap.get(chap_id)
            cached_chap = existing_chapter_map.get(chap_id)

            # Incremental optimization: if existing has this chapter with matching page count, reuse it
            if cached_pages and cached_chap and len(cached_pages) == cached_chap.page_count:
                for cached_p in cached_pages:
                    file_name = f"{global_page_index:05d}.{cached_p.ext}"
                    remote_pages.append(
                        RemotePage(
                            index=global_page_index,
                            url=cached_p.url,
                            file=file_name,
                            ext=cached_p.ext,
                            chapter=chap_id,
                        )
                    )
                    page_records.append(
                        PageRecord(
                            index=global_page_index,
                            file=file_name,
                            ext=cached_p.ext,
                            cached=False,
                            chapter=chap_id,
                        )
                    )
                    global_page_index += 1
                chapters.append(
                    Chapter(
                        id=chap_id,
                        index=ep_idx,
                        title=ep_title,
                        page_count=len(cached_pages),
                        start=ep_start,
                    )
                )
                continue

            if ep_idx > 1 and PICA_API_PACING_MS > 0:
                _apply_pacing(PICA_API_PACING_MS)

            ep_pages: list[dict[str, Any]] = []
            p = 1
            while True:
                if p > 1 and PICA_API_PACING_MS > 0:
                    _apply_pacing(PICA_API_PACING_MS)
                pages_data = self._request(
                    "GET",
                    f"comics/{comic_id}/order/{ep_order}/pages",
                    params={"page": p},
                )
                pages_container = pages_data.get("data", {}).get("pages", {})
                docs = pages_container.get("docs", [])
                ep_pages.extend(docs)
                total_p = int(pages_container.get("pages", 1))
                if p >= total_p or not docs or p >= 500:
                    break
                p += 1

            for doc in ep_pages:
                media = doc.get("media", {})
                file_server = (media.get("fileServer") or "").rstrip("/")
                path = (media.get("path") or "").lstrip("/")
                if not file_server or not path:
                    continue

                page_url = f"{file_server}/static/{path}"
                raw_ext = path.split(".")[-1].lower() if "." in path else "jpg"
                ext = raw_ext if raw_ext in ("jpg", "jpeg", "png", "webp") else "jpg"
                file_name = f"{global_page_index:05d}.{ext}"

                remote_pages.append(
                    RemotePage(
                        index=global_page_index,
                        url=page_url,
                        file=file_name,
                        ext=ext,
                        chapter=str(ep_order),
                    )
                )
                page_records.append(
                    PageRecord(
                        index=global_page_index,
                        file=file_name,
                        ext=ext,
                        cached=False,
                        chapter=str(ep_order),
                    )
                )
                global_page_index += 1

            chapters.append(
                Chapter(
                    id=str(ep_order),
                    index=ep_idx,
                    title=ep_title,
                    page_count=len(ep_pages),
                    start=ep_start,
                )
            )

        total_page_count = len(remote_pages)
        cover_count = min(COVER_COUNT, total_page_count) if total_page_count else COVER_COUNT
        # Dual-source cover fusion: Cover 1 uses official thumb (fallback to page 1), Cover 2~4 map to pages 1, 2, 3
        cover_indices = ([1] + list(range(1, cover_count)))[:cover_count] if total_page_count else []

        comic_meta = ComicMeta(
            source=self.key,
            source_id=comic_id,
            display_id=f"PICA_{comic_id}",
            title=title,
            authors=authors,
            works=[],
            actors=[],
            tags=tags,
            description=description,
            uploader=uploader,
            page_count=total_page_count,
            published_at=published_at,
            updated_at=updated_at,
            views=views,
            likes=likes,
            comment_count=int(comic_info.get("commentsCount", comic_info.get("totalComments", 0)) or 0),
            favorite=False,
            cover_count=cover_count,
            cover_indices=cover_indices,
            source_url=f"https://picawang.com/comic/{comic_id}",
            pages=page_records,
            chapters=chapters if len(chapters) > 1 else [],
            raw=comic_info,
        )

        return FetchedComic(meta=comic_meta, remote_pages=remote_pages)

    def download_cover(self, comic: FetchedComic) -> bytes | None:
        """Downloads the official cover thumbnail for PicAcg comic if available.
        Ref: https://github.com/wgh136/PicaComic (PicaComic by wgh136)
        """
        raw = comic.meta.raw if isinstance(comic.meta.raw, dict) else {}
        thumb = raw.get("thumb")
        if not thumb or not isinstance(thumb, dict):
            return None

        file_server = (thumb.get("fileServer") or "").rstrip("/")
        path = (thumb.get("path") or "").lstrip("/")
        if not file_server or not path:
            return None

        if path.startswith("static/"):
            target_url = f"{file_server}/{path}"
        else:
            target_url = f"{file_server}/static/{path}"

        return self.download_cover_by_url(target_url)


    def download_cover_by_url(self, cover_url: str) -> bytes | None:
        """Downloads cover image bytes directly from a verified cover URL with candidate CDN fallbacks."""
        if not cover_url or not cover_url.strip():
            return None
        parsed = urlparse(cover_url.strip())
        if parsed.scheme not in ("http", "https"):
            return None

        original_host = (parsed.hostname or "").lower()
        try:
            _validate_download_host(original_host)
        except ValueError:
            return None

        candidate_urls: list[str] = [cover_url.strip()]
        for fallback_host in PICA_STORAGE_FALLBACKS:
            if fallback_host != original_host:
                candidate_urls.append(parsed._replace(netloc=fallback_host).geturl())

        headers = {
            "User-Agent": "okhttp/3.8.1",
            "Referer": "https://www.picacomic.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }
        proxies = {"http": PICA_PROXY, "https": PICA_PROXY} if PICA_PROXY else None
        session = self._session()

        for url in candidate_urls:
            try:
                _validate_download_host((urlparse(url).hostname or "").lower())
                resp = session.get(url, headers=headers, proxies=proxies, timeout=15)
                if resp.status_code == 200 and len(resp.content) >= 100 and is_valid_image(resp.content):
                    return bytes(resp.content)
            except Exception as exc:
                logger.debug(f"下载哔咔发现封面分流节点异常 ({sanitize_proxy_url(url)}): {exc}")

        return None

    def download_page(self, comic: FetchedComic, page: RemotePage) -> bytes:
        """Downloads a single page image with multi-CDN failover and concurrency gate control."""
        parsed = urlparse(page.url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"非法的画页下载协议: {parsed.scheme}")

        original_host = (parsed.hostname or "").lower()
        _validate_download_host(original_host)

        # Construct candidate CDN endpoints in priority order using structured URL netloc replacement
        candidate_urls: list[str] = [page.url]
        for fallback_host in PICA_STORAGE_FALLBACKS:
            if fallback_host != original_host:
                candidate_urls.append(parsed._replace(netloc=fallback_host).geturl())

        headers = {
            "User-Agent": "okhttp/3.8.1",
            "Referer": "https://www.picacomic.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }
        proxies = {"http": PICA_PROXY, "https": PICA_PROXY} if PICA_PROXY else None

        session = self._session()
        last_error: Exception | None = None
        with download_gate:
            for url in candidate_urls:
                try:
                    resp = session.get(url, headers=headers, proxies=proxies, timeout=20)
                    if resp.status_code == 200 and len(resp.content) >= 100:
                        if is_valid_image(resp.content):
                            if PICA_DOWNLOAD_PACING_MS > 0:
                                _apply_pacing(PICA_DOWNLOAD_PACING_MS)
                            return bytes(resp.content)
                        logger.debug(
                            f"分流节点 {sanitize_proxy_url(url)} 响应非合法图片格式 "
                            f"(magic: {resp.content[:8]!r}, len: {len(resp.content)})，尝试下一个分流..."
                        )
                    else:
                        logger.debug(
                            f"分流节点 {sanitize_proxy_url(url)} 响应无效 "
                            f"(status: {resp.status_code}, len: {len(resp.content)})，尝试下一个分流..."
                        )
                except Exception as exc:
                    last_error = exc
                    logger.debug(
                        f"分流节点 {sanitize_proxy_url(url)} 异常: {sanitize_proxy_url(str(exc))}，尝试下一个分流..."
                    )

        safe_last_error = sanitize_proxy_url(str(last_error)) if last_error else "未知错误"
        raise RuntimeError(
            f"哔咔画页下载失败 (第 {page.index} 页): 遍历 {len(candidate_urls)} 个分流节点均无法获取。最后异常: {safe_last_error}"
        )

    def fetch_ranking(
        self,
        timeframe: str = "week",
        page: int = 1,
        limit: int = 50,
    ) -> list[DiscoveryItem]:
        """Fetches PicAcg leaderboard / trending comics.
        timeframe: 'day' (H24), 'week' (D7), 'month' (D30)
        """
        tt_map = {
            "day": "H24",
            "week": "D7",
            "month": "D30",
            "H24": "H24",
            "D7": "D7",
            "D30": "D30",
        }
        tt_val = tt_map.get(timeframe, "D7")
        try:
            data = self._request("GET", "comics/leaderboard", params={"tt": tt_val, "ct": "VC"})
        except Exception as exc:
            safe_err = sanitize_proxy_url(str(exc))
            logger.warning(f"获取哔咔排行榜失败 (tt={tt_val}): {safe_err}")
            raise RuntimeError(f"获取哔咔排行榜失败: {safe_err}") from exc

        comics = data.get("data", {}).get("comics", [])
        items: list[DiscoveryItem] = []
        for c in comics:
            source_id = str(c.get("_id") or "").strip()
            if not source_id:
                continue
            title = (c.get("title") or f"PicAcg_{source_id}").strip()
            author = (c.get("author") or "").strip()
            cats = c.get("categories") or []
            category = str(cats[0]).strip() if cats else ""
            thumb = c.get("thumb") or {}
            file_server = (thumb.get("fileServer") or "").rstrip("/")
            thumb_path = (thumb.get("path") or "").lstrip("/")
            if thumb_path.startswith("static/"):
                cover_url = f"{file_server}/{thumb_path}" if file_server else ""
            elif file_server and thumb_path:
                cover_url = f"{file_server}/static/{thumb_path}"
            else:
                cover_url = ""
            url = f"https://picawang.com/comic/{source_id}"

            items.append(
                DiscoveryItem(
                    id=f"picacg_{source_id}",
                    source_id=source_id,
                    source=self.key,
                    title=title,
                    author=author,
                    category=category,
                    cover_url=cover_url,
                    url=url,
                )
            )
            if len(items) >= limit:
                break

        return items
