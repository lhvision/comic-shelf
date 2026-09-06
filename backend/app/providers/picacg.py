from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
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
from ..models import Chapter, ComicMeta, FetchedComic, PageRecord, RemotePage
from .base import ComicProvider

logger = logging.getLogger(__name__)

PICA_API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"
PICA_SECRET_KEY = "~d}$Q7$eIni=V)9\\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn"
PICA_APP_VERSION = "2.2.1.3.3.4"
PICA_APP_BUILD_VERSION = "45"
PICA_APP_PLATFORM = "android"

PICA_STORAGE_FALLBACKS = [
    "storage1.bwaa.co",
    "storage.wikawika.xyz",
    "storage2.bwaa.co",
    "storage3.bwaa.co",
]


def calc_signature(path: str, nonce: str, time_str: str, method: str) -> str:
    """Calculates the HMAC-SHA256 signature required by PicAcg mobile REST API.

    The path should be the endpoint relative to the base URL (without query strings),
    lowercased along with the timestamp, nonce, method, and the mobile API key.
    """
    clean_path = path.lstrip("/").split("?")[0]
    raw = f"{clean_path}{time_str}{nonce}{method.upper()}{PICA_API_KEY}".lower()
    return hmac.new(
        PICA_SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


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

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_file = DATA_DIR / "picacg_session.json"

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
            m = re.search(r"([0-9a-fA-F]{24})", cleaned)
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
        try:
            if self._session_file.exists():
                data = json.loads(self._session_file.read_text(encoding="utf-8"))
                token = data.get("token")
                # Token valid for 7 days (604800 seconds)
                if token and time.time() - float(data.get("time", 0)) < 7 * 24 * 3600:
                    return str(token)
        except Exception as exc:
            logger.warning(f"读取哔咔本地 Session 失败: {exc}")
        return None

    def _save_token(self, token: str, email: str) -> None:
        try:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            self._session_file.write_text(
                json.dumps(
                    {
                        "token": token,
                        "email": email,
                        "time": time.time(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            try:
                self._session_file.chmod(0o600)
            except OSError:
                pass
        except Exception as exc:
            logger.warning(f"写入哔咔本地 Session 失败: {exc}")

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
        session = curl_requests.Session(impersonate="chrome")

        try:
            resp = session.post(
                url,
                json={"email": act_email, "password": act_pwd},
                headers=headers,
                proxies=proxies,
                timeout=15,
            )
        except Exception as exc:
            raise RuntimeError(f"连接哔咔登录服务器失败: {exc}。若在国内网络请确认 PICA_PROXY 是否已开启") from exc

        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                pass
            raise RuntimeError(f"哔咔登录失败 ({resp.status_code}): {err_msg}")

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
        """Sends an authenticated request to PicAcg REST API."""
        token = self.ensure_token()
        headers = self._create_headers(endpoint, method=method, token=token)
        url = f"{PICA_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        proxies = {"http": PICA_PROXY, "https": PICA_PROXY} if PICA_PROXY else None
        session = curl_requests.Session(impersonate="chrome")

        try:
            if method.upper() == "GET":
                resp = session.get(url, params=params, headers=headers, proxies=proxies, timeout=15)
            else:
                resp = session.post(url, json=json_data, headers=headers, proxies=proxies, timeout=15)
        except Exception as exc:
            raise RuntimeError(f"请求哔咔 API 失败 ({endpoint}): {exc}") from exc

        if resp.status_code == 401 and retry_auth:
            logger.warning("哔咔 Token 已过期，尝试重新登录...")
            with self._lock:
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
        views = str(comic_info.get("viewsCount", ""))
        likes = str(comic_info.get("likesCount", ""))
        updated_at = str(comic_info.get("updated_at") or comic_info.get("created_at") or "")

        # 2. Fetch all episode listings (with pagination)
        eps: list[dict[str, Any]] = []
        page = 1
        while True:
            eps_data = self._request("GET", f"comics/{comic_id}/eps", params={"page": page})
            eps_container = eps_data.get("data", {}).get("eps", {})
            docs = eps_container.get("docs", [])
            eps.extend(docs)
            total_pages = int(eps_container.get("pages", 1))
            if page >= total_pages or not docs:
                break
            page += 1

        # Sort episodes by natural order
        eps.sort(key=lambda x: int(x.get("order", 0)))

        # Fallback if no episodes returned (e.g. single-chapter legacy entry)
        if not eps:
            eps = [{"order": 1, "title": "第 1 話", "_id": comic_id}]

        chapters: list[Chapter] = []
        remote_pages: list[RemotePage] = []
        page_records: list[PageRecord] = []
        global_page_index = 1

        # 3. Fetch pages for each episode
        for ep_idx, ep in enumerate(eps, start=1):
            ep_order = int(ep.get("order", ep_idx))
            ep_title = (ep.get("title") or f"第 {ep_order} 話").strip()
            ep_start = global_page_index

            ep_pages: list[dict[str, Any]] = []
            p = 1
            while True:
                pages_data = self._request(
                    "GET",
                    f"comics/{comic_id}/order/{ep_order}/pages",
                    params={"page": p},
                )
                pages_container = pages_data.get("data", {}).get("pages", {})
                docs = pages_container.get("docs", [])
                ep_pages.extend(docs)
                total_p = int(pages_container.get("pages", 1))
                if p >= total_p or not docs:
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
            published_at="",
            updated_at=updated_at,
            views=views,
            likes=likes,
            comment_count=0,
            favorite=False,
            cover_count=COVER_COUNT,
            source_url=f"https://picawang.com/comic/{comic_id}",
            pages=page_records,
            chapters=chapters if len(chapters) > 1 else [],
            raw=comic_info,
        )

        return FetchedComic(meta=comic_meta, remote_pages=remote_pages)

    def download_page(self, comic: FetchedComic, page: RemotePage) -> bytes:
        """Downloads a single page image with multi-CDN failover and concurrency gate control."""
        parsed = urlparse(page.url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"非法的画页下载协议: {parsed.scheme}")

        original_host = (parsed.hostname or "").lower()
        if not original_host or original_host == "localhost":
            raise ValueError(f"禁止访问敏感或未知的画页下载目标: {original_host}")

        try:
            ip = ipaddress.ip_address(original_host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"禁止下载私有或回环网络地址图片: {original_host}")
        except ValueError:
            if original_host.endswith(".local") or original_host.endswith(".internal"):
                raise ValueError(f"禁止下载内部网络域名图片: {original_host}")

        # Construct candidate CDN endpoints in priority order
        candidate_urls: list[str] = [page.url]
        for fallback_host in PICA_STORAGE_FALLBACKS:
            if fallback_host != original_host:
                candidate_urls.append(page.url.replace(f"://{original_host}", f"://{fallback_host}"))

        headers = {
            "User-Agent": "okhttp/3.8.1",
            "Referer": "https://www.picacomic.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }
        proxies = {"http": PICA_PROXY, "https": PICA_PROXY} if PICA_PROXY else None

        last_error: Exception | None = None
        with download_gate:
            for url in candidate_urls:
                try:
                    session = curl_requests.Session(impersonate="chrome")
                    resp = session.get(url, headers=headers, proxies=proxies, timeout=20)
                    if resp.status_code == 200 and len(resp.content) > 0:
                        return bytes(resp.content)
                    logger.debug(f"分流节点 {url} 返回 HTTP {resp.status_code}，尝试下一个分流...")
                except Exception as exc:
                    last_error = exc
                    logger.debug(f"分流节点 {url} 异常: {exc}，尝试下一个分流...")

        raise RuntimeError(
            f"哔咔画页下载失败 (第 {page.index} 页): 遍历 {len(candidate_urls)} 个分流节点均无法获取。最后异常: {last_error}"
        )
