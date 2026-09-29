from __future__ import annotations

import ipaddress
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


def aes_decrypt(key_str: str, cipher_hex_with_iv: str) -> str:
    key = key_str.encode("utf-8")
    iv = cipher_hex_with_iv[:16].encode("utf-8")
    ciphertext = bytes.fromhex(cipher_hex_with_iv[16:])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")

from ..config import (
    COPY_BASE_URL,
    COPY_PASSWORD,
    COPY_TOKEN,
    COPY_USERNAME,
    COVER_COUNT,
    DATA_DIR,
    get_proxy_for_source,
)
from ..gate import download_gate
from ..models import Chapter, ComicMeta, FetchedComic, PageRecord, RemotePage
from .base import ComicProvider

logger = logging.getLogger("paper_room.provider.copymanga")

SESSION_FILE = DATA_DIR / "copymanga_session.json"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def is_valid_image(data: bytes) -> bool:
    """Validate image magic bytes to reject corrupted bytes or HTML/WAF error blocks."""
    if not data or len(data) < 4:
        return False
    if data[:3] == b"\xff\xd8\xff":
        return True
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return True
    return False


def _validate_download_host(host: str) -> None:
    """SSRF defense: block private networks, localhost, link-local, and pseudo-domains."""
    cleaned = (host or "").strip().lower()
    if not cleaned or cleaned in ("localhost", "localtest.me"):
        raise ValueError(f"禁止访问敏感或未知的画页下载目标: {host}")

    try:
        ip = ipaddress.ip_address(cleaned)
        is_ip = True
    except ValueError:
        is_ip = False

    if is_ip:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError(f"禁止下载私有或保留网络地址图片: {host}")
        raise ValueError(f"禁止使用直接 IP 地址访问画页 CDN: {host}")

    if cleaned.endswith(
        (".local", ".internal", ".lan", ".home", ".corp", ".onion", ".nip.io", ".sslip.io")
    ):
        raise ValueError(f"禁止下载内部网络或重绑定域名图片: {host}")


class CopyMangaProvider(ComicProvider):
    """拷贝漫画 (CopyManga) Provider implementation."""

    key = "copymanga"
    label = "拷贝漫画"
    short_label = "拷贝"
    id_pattern = r"^[a-zA-Z0-9_\-\.]+$"
    example = "xiangyaochengweiyingzhishilizhe"

    def __init__(self) -> None:
        self._tls = threading.local()

    @property
    def base_url(self) -> str:
        return COPY_BASE_URL.rstrip("/")

    @property
    def proxy(self) -> str:
        return get_proxy_for_source("copymanga")

    def _session(self) -> curl_requests.Session:
        sess = getattr(self._tls, "session", None)
        if sess is None:
            sess = curl_requests.Session(impersonate="chrome")
            self._tls.session = sess
        return sess

    def _get_token(self) -> str:
        """Resolve authentication token: explicit COPY_TOKEN > saved session > optional auto-login."""
        if COPY_TOKEN:
            return COPY_TOKEN

        saved = self.load_secure_session(SESSION_FILE)
        if saved and isinstance(saved, dict):
            token = saved.get("token")
            if token and isinstance(token, str):
                return token.strip()

        # Optional auto-login if username and password are provided
        if COPY_USERNAME and COPY_PASSWORD:
            try:
                token = self._login(COPY_USERNAME, COPY_PASSWORD)
                if token:
                    self.save_secure_session(SESSION_FILE, {"token": token, "username": COPY_USERNAME})
                    return token
            except Exception as exc:
                logger.warning("拷贝漫画自动登录失败: %s", exc)

        return ""

    def _login(self, username: str, password: str) -> str:
        """Attempt login via official /api/v1/login endpoint."""
        url = f"{self.base_url}/api/v1/login"
        payload = {"username": username, "password": password, "salt": "", "code": ""}
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        resp = self._session().post(
            url,
            data=payload,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Referer": f"{self.base_url}/login",
            },
            proxies=proxies,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                results = data.get("results", {})
                token = results.get("token") or results.get("uuid")
                if token:
                    return str(token)
            msg = data.get("message") or "未知错误"
            raise RuntimeError(f"拷贝漫画登录返回失败: {msg}")
        raise RuntimeError(f"拷贝漫画登录 HTTP 异常: {resp.status_code}")

    def _get_headers(self, referer: str | None = None, is_api: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": referer or f"{self.base_url}/",
        }
        if is_api:
            headers["Accept"] = "application/json, text/plain, */*"
            headers["X-Requested-With"] = "XMLHttpRequest"
        else:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        token = self._get_token()
        if token:
            headers["Authorization"] = f"Token {token}"
            headers["Cookie"] = f"token={token}; webp=1"
        return headers

    def normalize_id(self, raw: str) -> str:
        """Turn user input into the canonical provider id (pathword slug)."""
        cleaned = (raw or "").strip()
        if not cleaned:
            raise ValueError("拷贝漫画车号不能为空")

        # 1. Full URL matching (e.g. https://www.mangacopy.com/comic/xiangyaochengweiyingzhishilizhe/...)
        url_match = re.search(r"/comic/([a-zA-Z0-9_\-\.]+)", cleaned)
        if url_match:
            cleaned = url_match.group(1)

        # 2. Prefix stripping (e.g. copymanga:, copy:, copy_, copymanga_)
        cleaned = re.sub(r"^(?:copymanga|copy)[:_\-\s]+", "", cleaned, flags=re.IGNORECASE)

        # 3. Strip query parameters, hashes, and trailing slashes
        cleaned = cleaned.split("?")[0].split("#")[0].rstrip("/")

        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", cleaned):
            raise ValueError(f"非法的拷贝漫画车号标识: '{raw}'，期望为字母/数字/下划线/连字符组成的 slug")

        return cleaned

    def fetch(
        self,
        raw_id: str,
        *,
        existing: FetchedComic | None = None,
        groups_to_fetch: list[str] | None = None,
        **kwargs: Any,
    ) -> FetchedComic:
        """Fetch metadata + page URLs for a CopyManga comic."""
        comic_id = self.normalize_id(raw_id)
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None

        # 1. Fetch comic detail HTML page
        detail_url = f"{self.base_url}/comic/{comic_id}"
        resp = self._session().get(
            detail_url,
            headers=self._get_headers(referer=f"{self.base_url}/"),
            proxies=proxies,
            timeout=15,
        )

        if resp.status_code == 404 or "404 Not Found" in resp.text:
            raise ValueError(f"拷贝漫画作品不存在或已下架: {comic_id}")
        if resp.status_code != 200:
            raise RuntimeError(f"请求拷贝漫画主页失败 ({resp.status_code}): {detail_url}")

        html = resp.text

        # 2. Parse title
        title = ""
        h6_match = re.search(r"<h6[^>]*title=[\"']([^\"']+)[\"']", html)
        if h6_match:
            title = h6_match.group(1).strip()
        if not title:
            h6_text = re.search(r"<h6[^>]*>(.*?)</h6>", html, re.DOTALL)
            if h6_text:
                title = re.sub(r"<[^>]+>", "", h6_text.group(1)).strip()
        if not title:
            title_tag = re.search(r"<title>(.*?)</title>", html)
            if title_tag:
                title = title_tag.group(1).split("-")[0].strip()
        title = title or f"CopyManga_{comic_id}"

        # 3. Parse authors
        authors: list[str] = []
        for author_match in re.finditer(r'<a\s+href=[\'"]/author/[^\'"]+/comics[\'"][^>]*>([^<]+)</a>', html):
            author_name = author_match.group(1).strip()
            if author_name and author_name not in authors:
                authors.append(author_name)
        author = " / ".join(authors) if authors else ""

        # 4. Parse cover URL
        cover_url = ""
        cover_match = re.search(r'<img[^>]*class=[\'"][^\'"]*lazyload[^\'"]*[\'"][^>]*data-src=[\'"]([^\'"]+)[\'"]', html)
        if cover_match:
            cover_url = cover_match.group(1).strip()
        if not cover_url:
            any_cover = re.search(r'<img[^>]*data-src=[\'"]([^\'"]+cover[^\'"]*)[\'"]', html)
            if any_cover:
                cover_url = any_cover.group(1).strip()

        # 5. Parse tags (themes and status)
        tags: list[str] = []
        themes = re.findall(
            r"href=[\x27\x22]/comics\?theme=[^\x27\x22]+[\x27\x22][^>]*>#?([^<]+)</a>",
            html,
        )
        for t in themes:
            t_clean = t.strip().lstrip("#")
            if t_clean and t_clean not in tags:
                tags.append(t_clean)

        status_match = re.search(
            r"狀態[：:]\s*</span>\s*<span[^>]*comicParticulars-right-txt[^>]*>([^<]+)</span>",
            html,
        )
        status = status_match.group(1).strip() if status_match else ""
        if status and status not in tags:
            tags.append(status)

        # 6. Parse description
        description = ""
        intro_match = re.search(r'<p\s+class=[\'"]intro[\'"][^>]*>(.*?)</p>', html, re.DOTALL)
        if intro_match:
            description = re.sub(r"<[^>]+>", "", intro_match.group(1)).strip()

        # 7. Parse views (heat) and updated / published dates
        views = ""
        views_match = re.search(
            r"熱度[：:]\s*</span>\s*<p[^>]*comicParticulars-right-txt[^>]*>.*?([0-9\.]+\s*[a-zA-Z万Ww]+)",
            html,
            re.DOTALL,
        )
        if views_match:
            views = views_match.group(1).strip()

        updated_at = ""
        upd_match = re.search(
            r"最後更新[：:]\s*</span>\s*<span[^>]*comicParticulars-right-txt[^>]*>(\d{4}-\d{2}-\d{2})",
            html,
        )
        if upd_match:
            updated_at = upd_match.group(1).strip()

        # CopyManga only provides last updated date ("最後更新"), published date is left blank
        published_at = ""

        # 8. Extract dynamic encryption parameters (ccz and dnt)
        ccz_match = re.search(r"var\s+ccz\s*=\s*[\"']([^\"']+)[\"']", html)
        if not ccz_match:
            raise RuntimeError(f"无法从拷贝漫画作品页面中解析出解密密钥 (ccz): {comic_id}")
        ccz = ccz_match.group(1).strip()

        dnt_match = re.search(r'id=[\'"]dnt[\'"][^>]*value=[\'"]([^\'"]+)[\'"]', html)
        if not dnt_match:
            dnt_match = re.search(r'value=[\'"]([^\'"]+)[\'"][^>]*id=[\'"]dnt[\'"]', html)
        dnt = dnt_match.group(1).strip() if dnt_match else "1"

        # 9. Request chapters list API
        chapters_api_url = f"{self.base_url}/comicdetail/{comic_id}/chapters"
        ch_resp = self._session().get(
            chapters_api_url,
            headers={
                **self._get_headers(referer=detail_url, is_api=True),
                "dnts": dnt,
            },
            proxies=proxies,
            timeout=15,
        )

        if ch_resp.status_code != 200:
            raise RuntimeError(f"请求拷贝漫画章节列表接口失败 ({ch_resp.status_code}): {chapters_api_url}")

        ch_data = ch_resp.json()
        if ch_data.get("code") != 200:
            msg = ch_data.get("message") or "请求异常"
            raise RuntimeError(f"拷贝漫画章节接口返回错误: {msg}")

        encrypted_results = ch_data.get("results", "")
        if not encrypted_results:
            raise RuntimeError("拷贝漫画章节接口未返回加密数据 (results)")

        try:
            decrypted_chapters_json = aes_decrypt(ccz, encrypted_results)
            chapters_info = json.loads(decrypted_chapters_json)
        except Exception as exc:
            raise RuntimeError(f"解密拷贝漫画章节列表失败: {exc}") from exc

        groups = chapters_info.get("groups", {})
        if not groups:
            raise ValueError(f"拷贝漫画作品 {comic_id} 未找到任何章节分组")

        # 10. Extract available groups and filter target groups
        ordered_group_keys = []
        if "default" in groups:
            ordered_group_keys.append("default")
        for g_k in groups:
            if g_k not in ordered_group_keys:
                ordered_group_keys.append(g_k)

        available_groups: list[dict[str, Any]] = []
        for g_k in ordered_group_keys:
            g_data = groups[g_k]
            g_name = (g_data.get("name") or g_k).strip()
            ch_list = g_data.get("chapters", [])
            available_groups.append(
                {
                    "key": g_k,
                    "name": g_name,
                    "count": len(ch_list),
                }
            )

        # Decide which groups to include (default policy: default/serialized only)
        if groups_to_fetch is not None:
            target_groups = [g for g in ordered_group_keys if g in groups_to_fetch]
            if not target_groups and ordered_group_keys:
                target_groups = [ordered_group_keys[0]]
        elif (
            existing is not None
            and isinstance(existing.meta.raw, dict)
            and "selected_groups" in existing.meta.raw
        ):
            saved_groups = existing.meta.raw.get("selected_groups", [])
            target_groups = [g for g in ordered_group_keys if g in saved_groups]
            if not target_groups and ordered_group_keys:
                target_groups = ["default"] if "default" in ordered_group_keys else [ordered_group_keys[0]]
        else:
            target_groups = ["default"] if "default" in ordered_group_keys else [ordered_group_keys[0]]

        selected_groups = target_groups

        flattened_raw_chapters: list[dict[str, Any]] = []
        multi_groups = len(selected_groups) > 1

        for g_k in selected_groups:
            g_data = groups[g_k]
            g_name = (g_data.get("name") or g_k).strip()
            ch_list = g_data.get("chapters", [])
            for ch in ch_list:
                cid = str(ch.get("id") or "").strip()
                cname = str(ch.get("name") or "").strip()
                if not cid:
                    continue
                display_name = f"[{g_name}] {cname}" if (multi_groups and g_k != "default") else cname
                flattened_raw_chapters.append(
                    {
                        "id": cid,
                        "name": display_name,
                        "group": g_k,
                        "type": ch.get("type", 1),
                    }
                )

        if not flattened_raw_chapters:
            raise ValueError(f"拷贝漫画作品 {comic_id} 选定分组中未包含任何有效章节")

        # 11. Incremental cache check (reusing existing unchanged chapter pages)
        existing_chapter_map = {
            c.id: c for c in (existing.meta.chapters if existing else [])
        }
        existing_pages_by_chap: dict[str, list[RemotePage]] = {}
        if existing:
            for p in existing.remote_pages:
                if p.chapter:
                    existing_pages_by_chap.setdefault(p.chapter, []).append(p)

        def _fetch_chapter_pages(chap_item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
            cid = chap_item["id"]
            # Check if we can reuse existing
            if cid in existing_chapter_map and cid in existing_pages_by_chap:
                cached_pages = existing_pages_by_chap[cid]
                if cached_pages:
                    return chap_item, [p.url for p in cached_pages]

            chap_url = f"{self.base_url}/comic/{comic_id}/chapter/{cid}"
            sess = self._session()
            c_resp = sess.get(
                chap_url,
                headers=self._get_headers(referer=detail_url),
                proxies=proxies,
                timeout=15,
            )

            if c_resp.status_code != 200:
                raise RuntimeError(f"请求拷贝漫画单话失败 ({c_resp.status_code}): {chap_url}")

            chap_html = c_resp.text
            cct_match = re.search(r"var\s+cct\s*=\s*[\"']([^\"']+)[\"']", chap_html)
            ckey_match = re.search(r"var\s+contentKey\s*=\s*[\"']([^\"']+)[\"']", chap_html)

            if not cct_match or not ckey_match:
                # Check for login requirement
                if "登錄" in chap_html or "登录" in chap_html or "login" in chap_html:
                    raise ValueError(
                        f"拷贝漫画章节「{chap_item['name']}」受权限保护（需登录查看），请在配置中填入 COPY_TOKEN"
                    )
                raise RuntimeError(f"无法解析章节「{chap_item['name']}」画页加密密钥与内容")

            cct = cct_match.group(1).strip()
            ckey = ckey_match.group(1).strip()

            try:
                decrypted_pages_str = aes_decrypt(cct, ckey)
                pages_arr = json.loads(decrypted_pages_str)
                urls = [item["url"] for item in pages_arr if isinstance(item, dict) and "url" in item]
                return chap_item, urls
            except Exception as exc:
                raise RuntimeError(f"解密章节「{chap_item['name']}」画页列表失败: {exc}") from exc

        # 12. Fetch all chapters with concurrency pool (3 polite workers)
        fetched_chapter_pages: dict[str, list[str]] = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            future_to_ch = {
                pool.submit(_fetch_chapter_pages, ch): ch
                for ch in flattened_raw_chapters
            }
            for fut in as_completed(future_to_ch):
                ch_item, urls = fut.result()
                fetched_chapter_pages[ch_item["id"]] = urls

        # 13. Assemble final Chapter, RemotePage, PageRecord lists
        chapters: list[Chapter] = []
        remote_pages: list[RemotePage] = []
        page_records: list[PageRecord] = []
        global_page_index = 1

        for idx, ch in enumerate(flattened_raw_chapters, start=1):
            cid = ch["id"]
            title_text = ch["name"]
            page_urls = fetched_chapter_pages.get(cid, [])
            start_page = global_page_index

            chapters.append(
                Chapter(
                    id=cid,
                    index=idx,
                    title=title_text,
                    page_count=len(page_urls),
                    start=start_page,
                    group=ch.get("group"),
                )
            )

            for page_idx, p_url in enumerate(page_urls, start=1):
                parsed = urlparse(p_url)
                raw_ext = Path(parsed.path).suffix.lower().lstrip(".") or "jpg"
                ext = raw_ext if raw_ext in ("jpg", "jpeg", "png", "webp", "avif") else "jpg"
                file_name = f"{global_page_index:05d}.{ext}"

                remote_pages.append(
                    RemotePage(
                        index=global_page_index,
                        url=p_url,
                        file=file_name,
                        ext=ext,
                        chapter=cid,
                        headers={"Referer": f"{self.base_url}/"},
                    )
                )

                page_records.append(
                    PageRecord(
                        index=global_page_index,
                        file=file_name,
                        ext=ext,
                        cached=False,
                        chapter=cid,
                    )
                )

                global_page_index += 1

        total_pages = len(page_records)
        effective_cover_count = min(COVER_COUNT, total_pages) if total_pages > 0 else 0

        # Construct final pure domain ComicMeta
        meta = ComicMeta(
            source=self.key,
            source_id=comic_id,
            display_id=f"COPY_{comic_id}",
            title=title,
            authors=authors,
            works=[],
            actors=[],
            tags=tags,
            description=description,
            uploader=None,
            page_count=total_pages,
            cover_count=effective_cover_count,
            cover_indices=[i for i in range(1, effective_cover_count + 1)],
            published_at=published_at,
            updated_at=updated_at,
            views=views,
            likes="",
            chapters=chapters if len(chapters) > 1 else [],
            pages=page_records,
            source_url=f"{self.base_url}/comic/{comic_id}",
            raw={
                "base_url": self.base_url,
                "cover_url": cover_url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "available_groups": available_groups,
                "selected_groups": selected_groups,
            },
        )

        return FetchedComic(
            meta=meta,
            remote_pages=remote_pages,
            decode_version=2,  # Already clean un-scrambled bytes
        )

    def download_page(self, comic: FetchedComic, page: RemotePage) -> bytes:
        """Download one page and return valid image bytes."""
        url = page.url
        if not url:
            raise ValueError(f"画页缺少有效的下载 URL (page {page.index})")

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"非法的画页下载协议: {parsed.scheme}")

        _validate_download_host(parsed.netloc)

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": (page.headers or {}).get("Referer") or f"{self.base_url}/",
        }

        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None

        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                with download_gate:
                    resp = self._session().get(
                        url,
                        headers=headers,
                        proxies=proxies,
                        timeout=20,
                    )
                if resp.status_code == 200:
                    data = resp.content
                    if not is_valid_image(data):
                        raise ValueError(f"下载的画页非有效图片格式 (Magic Bytes 校验失败): {url}")
                    return data
                raise RuntimeError(f"下载画页失败 ({resp.status_code}): {url}")
            except Exception as exc:
                last_exc = exc
                if attempt == 0 and not isinstance(exc, ValueError):
                    time.sleep(0.5)

        raise last_exc or RuntimeError(f"下载画页失败: {url}")
