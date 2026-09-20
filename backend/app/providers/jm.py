from __future__ import annotations

import html as html_lib
import ipaddress
import json
import logging
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
import threading
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

from ..config import (
    COVER_COUNT,
    DATA_DIR,
    JM_IMAGE_PROXY_MODE,
    JM_PASSWORD,
    JM_PROXY,
    JM_USERNAME,
)
from ..gate import download_gate
from ..models import Chapter, ComicMeta, DiscoveryItem, FetchedComic, RemotePage
from ..formatting import format_count
from .base import ComicProvider

logger = logging.getLogger("paper_room.provider.jm")

try:
    from jmcomic import JmModuleConfig

    JmModuleConfig.disable_jm_log()
except ImportError:
    pass

_JM_REDIRECT_URL = "https://jm365.work/3YeBdF"
_FALLBACK_HTML_DOMAINS = [
    "comic18j-rita.cc",
    "18comic.vip",
    "18comic.org",
]
_DOMAIN_TTL_SECONDS = 6 * 60 * 60
_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
_PROXY_CRED_RE = re.compile(r"://([^:@\s]*):([^@\s]+)@")


def sanitize_proxy_url(text: str) -> str:
    """Mask credentials (username:password) in proxy URLs or error messages."""
    return _PROXY_CRED_RE.sub(r"://\1:***@", text)


def _mask_sensitive(text: object) -> str:
    """Mask passwords and credentials in logs and exception messages."""
    if text is None:
        return ""
    s = sanitize_proxy_url(str(text))
    if JM_PASSWORD and len(JM_PASSWORD) >= 4 and JM_PASSWORD in s:
        s = s.replace(JM_PASSWORD, "***")
    elif JM_PASSWORD and len(JM_PASSWORD) < 4 and JM_PASSWORD in s:
        s = s.replace(f":{JM_PASSWORD}@", ":***@").replace(f"={JM_PASSWORD}", "=***")
    return s


def _is_safe_remote_domain(domain: str) -> bool:
    """Validate that a domain is a safe public hostname.

    Protects against SSRF and DNS/captive portal hijacking redirecting to LAN,
    loopback, link-local, or cloud metadata endpoints (PITFALLS.md #59).
    """
    if not domain or len(domain) > 253:
        return False
    d = domain.strip().lower()

    # Block URI components, credentials, query, hash, and path traversal tokens anywhere in domain
    if any(c in d for c in "/?#@%"):
        return False

    # Handle IPv6 brackets or trailing port (e.g. "[::1]:8080" or "127.0.0.1:8080")
    if d.startswith("[") and "]" in d:
        host_part = d[1 : d.index("]")]
    else:
        host_part = d.split(":")[0]

    if host_part in {"jm-88.cc", "localhost", "broadcasthost"}:
        return False

    # Check for direct IP addresses
    try:
        ip = ipaddress.ip_address(host_part)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or (
                hasattr(ip, "ipv4_mapped")
                and ip.ipv4_mapped
                and (
                    ip.ipv4_mapped.is_private
                    or ip.ipv4_mapped.is_loopback
                    or ip.ipv4_mapped.is_link_local
                )
            )
        ):
            return False
        return True
    except ValueError:
        pass

    # If the last segment is purely numeric, it's an invalid or obfuscated IP (e.g. 0177.0.0.1)
    parts = host_part.split(".")
    if len(parts) > 1 and parts[-1].isdigit():
        return False

    # Block private and internal TLDs
    if host_part.endswith(
        (
            ".local",
            ".internal",
            ".lan",
            ".arpa",
            ".invalid",
            ".test",
            ".home.arpa",
        )
    ):
        return False

    if "." not in host_part:
        return False

    # RFC 1123 / RFC 1035 standard hostname validation
    if not re.match(
        r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$",
        host_part,
    ):
        return False

    return True


class JMProvider(ComicProvider):
    """禁漫天堂 provider.

    Metadata comes from the HTML album page (it contains the uploader,
    dates, formatted views/likes and the real photo image URL list).
    """

    key = "jm"
    label = "禁漫天堂 (JMComic)"
    short_label = "禁漫"
    id_pattern = r"^(?:JM)?(\d{5,8})$"
    example = "JM523607"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._domain_cache_file = DATA_DIR / "jm_html_domain.json"
        self._session_cache_file = DATA_DIR / "jm_session.json"

    # ------------------------------------------------------------------
    # proxy & network routing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sanitize_proxy(proxy: str) -> str:
        p = proxy.strip()
        if not p:
            return ""
        if not (
            p.startswith("http://")
            or p.startswith("https://")
            or p.startswith("socks5://")
            or p.startswith("socks5h://")
        ):
            p = f"http://{p}"
        return p

    def _get_control_proxies(self) -> dict[str, str] | None:
        p = self._sanitize_proxy(JM_PROXY)
        return {"http": p, "https": p} if p else None

    def _get_image_proxies(self) -> dict[str, str] | None:
        if JM_IMAGE_PROXY_MODE.lower() == "direct":
            return None
        # default "auto": follow JM_PROXY
        p = self._sanitize_proxy(JM_PROXY)
        return {"http": p, "https": p} if p else None

    # ------------------------------------------------------------------
    # session & authentication lifecycle
    # ------------------------------------------------------------------
    def _load_session_cache(self) -> dict[str, str] | None:
        data = self.load_secure_session(self._session_cache_file)
        if not data or data.get("username") != JM_USERNAME:
            return None
        try:
            ts = float(data.get("ts") or 0)
        except (TypeError, ValueError):
            return None
        if time.time() - ts < _SESSION_TTL_SECONDS:
            cookies = data.get("cookies")
            if isinstance(cookies, dict) and cookies:
                return {str(k): str(v) for k, v in cookies.items()}
        return None

    def _save_session_cache(self, cookies: dict[str, str]) -> None:
        self.save_secure_session(
            self._session_cache_file,
            {
                "cookies": cookies,
                "username": JM_USERNAME,
                "ts": time.time(),
            },
        )

    def _clear_session_cache(self) -> None:
        self.clear_secure_session(self._session_cache_file)

    def _get_valid_cookies(self, option=None, force_refresh: bool = False) -> dict[str, str] | None:
        if not JM_USERNAME or not JM_PASSWORD:
            return None

        if not force_refresh:
            cached = self._load_session_cache()
            if cached is not None:
                return cached

        with self._lock:
            cached = self._load_session_cache()
            if cached is not None:
                if not force_refresh:
                    return cached
                # 若已有其他并发线程在近 15 秒内刚刚完成登录自愈，直接复用避免惊群重登
                data = self.load_secure_session(self._session_cache_file) or {}
                try:
                    ts = float(data.get("ts") or 0)
                except (TypeError, ValueError):
                    ts = 0.0
                if time.time() - ts < 15:
                    return cached
            return self._perform_login(option)

    def _perform_login(self, option=None) -> dict[str, str] | None:
        if not JM_USERNAME or not JM_PASSWORD:
            return None
        try:
            from jmcomic import JmOption

            opt = option or JmOption.default()
            control_proxies = self._get_control_proxies()
            opt.client.postman.meta_data["proxies"] = control_proxies

            cookies: dict[str, str] = {}
            # 优先尝试 API 客户端登录，失败则降级到 HTML 客户端登录
            try:
                api_client = opt.build_jm_client(impl="api")
                api_client.login(JM_USERNAME, JM_PASSWORD)
                meta_cookies = api_client.get_meta_data("cookies")
                if isinstance(meta_cookies, dict):
                    cookies.update({str(k): str(v) for k, v in meta_cookies.items()})
            except Exception as e_api:
                logger.warning("禁漫 API 客户端登录失败，尝试 HTML 网页登录: %s", _mask_sensitive(e_api))
                try:
                    domain = self.resolve_html_domain()
                    html_client = opt.new_jm_client(impl="html", domain_list=[domain])
                    html_client.login(JM_USERNAME, JM_PASSWORD)
                    meta_cookies = html_client.get_meta_data("cookies")
                    if isinstance(meta_cookies, dict):
                        cookies.update({str(k): str(v) for k, v in meta_cookies.items()})
                except Exception as e_html:
                    logger.warning("禁漫 HTML 网页登录亦失败: %s", _mask_sensitive(e_html))
                    return None

            if cookies:
                self._save_session_cache(cookies)
                logger.info("禁漫账号登录成功，会话凭据已持久化缓存")
                return cookies
        except Exception as exc:
            logger.warning("禁漫登录流程异常: %s", _mask_sensitive(exc))
            return None
        return None

    # ------------------------------------------------------------------
    # id / domain helpers
    # ------------------------------------------------------------------
    def normalize_id(self, raw: str) -> str:
        m = re.fullmatch(self.id_pattern, raw.strip(), re.IGNORECASE)
        if m is None:
            raise ValueError("禁漫车号格式不正确，示例：JM523607 或 523607")
        return m.group(1)

    def _cached_html_domain(self) -> str | None:
        try:
            data = json.loads(self._domain_cache_file.read_text(encoding="utf-8"))
            if time.time() - float(data.get("ts", 0)) < _DOMAIN_TTL_SECONDS:
                return str(data["domain"])
        except Exception:
            return None
        return None

    def _write_html_domain(self, domain: str) -> None:
        try:
            self._domain_cache_file.write_text(
                json.dumps({"domain": domain, "ts": time.time()}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def resolve_html_domain(self) -> str:
        cached = self._cached_html_domain()
        if cached is not None:
            return cached

        with self._lock:
            cached = self._cached_html_domain()
            if cached is not None:
                return cached

            domain = ""
            with curl_requests.Session(impersonate="chrome") as session:
                proxies = self._get_control_proxies()
                if proxies:
                    session.proxies = proxies

                try:
                    resp = session.get(
                        _JM_REDIRECT_URL,
                        timeout=15,
                        allow_redirects=True,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0 Safari/537.36"
                            )
                        },
                    )
                    parsed = urlparse(str(resp.url))
                    cand_domain = parsed.hostname or ""
                    if cand_domain and _is_safe_remote_domain(cand_domain):
                        domain = cand_domain
                except Exception:
                    domain = ""

                if not domain:
                    for candidate in _FALLBACK_HTML_DOMAINS:
                        try:
                            probe = session.get(
                                f"https://{candidate}/",
                                timeout=4,
                                allow_redirects=True,
                            )
                            if probe.status_code == 200 and len(probe.content) > 1000:
                                cand_domain = urlparse(str(probe.url)).hostname or candidate
                                if cand_domain and _is_safe_remote_domain(cand_domain):
                                    domain = cand_domain
                                    break
                        except Exception:
                            continue

            if not domain:
                raise RuntimeError("无法找到可用的禁漫网页域名，请检查网络连接或配置 JM_PROXY")

            self._write_html_domain(domain)
            return domain

    # ------------------------------------------------------------------
    # fetching
    # ------------------------------------------------------------------
    def _make_api_client(self, force_refresh_session: bool = False):
        from jmcomic import JmOption

        option = JmOption.default()
        control_proxies = self._get_control_proxies()
        option.client.postman.meta_data["proxies"] = control_proxies

        cookies = self._get_valid_cookies(option, force_refresh=force_refresh_session)
        if cookies:
            option.update_cookies(cookies)

        return option.new_jm_client(impl="api")

    def _make_html_client(self, force_refresh_session: bool = False):
        from jmcomic import JmOption

        option = JmOption.default()
        control_proxies = self._get_control_proxies()
        option.client.postman.meta_data["proxies"] = control_proxies

        cookies = self._get_valid_cookies(option, force_refresh=force_refresh_session)
        if cookies:
            option.update_cookies(cookies)

        return option.new_jm_client(impl="html", domain_list=[self.resolve_html_domain()])

    @staticmethod
    def _parse_uploader(text: str) -> str | None:
        patterns = [
            re.compile(r"<(?:h2|span)[^>]*>\s*(?:上传者|上傳者)：?\s*</(?:h2|span)>\s*([^<\s][^<]*)", re.I),
            re.compile(r"(?:上传者|上傳者)[：:]\s*([^<\s][^<]*)", re.I),
        ]
        for pattern in patterns:
            m = pattern.search(text)
            if m is not None:
                value = html_lib.unescape(m.group(1)).strip()
                if value:
                    return value
        return None

    def _fetch_via_api(
        self,
        jm_id: str,
        *,
        existing: FetchedComic | None = None,
    ) -> FetchedComic:
        from jmcomic import MissingAlbumPhotoException

        api_client = self._make_api_client()

        try:
            detail = api_client.get_album_detail(jm_id)
        except MissingAlbumPhotoException as e_missing:
            if JM_USERNAME and JM_PASSWORD:
                logger.info("检测到受限车号 JM%s 在 API 端返回缺失，尝试自愈刷新凭据重试...", jm_id)
                self._clear_session_cache()
                api_client = self._make_api_client(force_refresh_session=True)
                try:
                    detail = api_client.get_album_detail(jm_id)
                except Exception:
                    raise e_missing
            else:
                raise

        def fetch_photo_api(pid: str):
            nonlocal api_client
            try:
                photo = api_client.get_photo_detail(pid, fetch_album=False)
                photo.from_album = detail
                return photo
            except MissingAlbumPhotoException as e_ep_missing:
                if JM_USERNAME and JM_PASSWORD:
                    logger.info("检测到单话 %s 在 API 端受限或缺失，尝试自愈刷新重登...", pid)
                    self._clear_session_cache()
                    api_client = self._make_api_client(force_refresh_session=True)
                    try:
                        photo = api_client.get_photo_detail(pid, fetch_album=False)
                        photo.from_album = detail
                        return photo
                    except Exception:
                        raise e_ep_missing
                else:
                    raise

        html_domain = self._cached_html_domain() or "18comic.vip"
        source_url = f"https://{html_domain}/album/{jm_id}"

        return self._assemble_fetched_comic(
            jm_id=jm_id,
            detail=detail,
            fetch_photo=fetch_photo_api,
            existing=existing,
            uploader=None,
            source_url=source_url,
        )

    def _fetch_via_html(
        self,
        jm_id: str,
        *,
        existing: FetchedComic | None = None,
    ) -> FetchedComic:
        from jmcomic import JmcomicText

        client = self._make_html_client()

        def _is_restricted(resp) -> bool:
            url_str = str(getattr(resp, "url", ""))
            text = getattr(resp, "text", "")
            return (
                "/login" in url_str
                or "需要登入" in text
                or "需要登录" in text
                or "登入後才能" in text
                or "登录后才能" in text
                or "請先登入" in text
                or "请先登录" in text
            )

        album_resp = client.get(f"/album/{jm_id}")
        if _is_restricted(album_resp):
            if JM_USERNAME and JM_PASSWORD:
                logger.info("检测到受限车号 JM%s，尝试 HTML 会话自愈刷新重登并重试...", jm_id)
                self._clear_session_cache()
                client = self._make_html_client(force_refresh_session=True)
                album_resp = client.get(f"/album/{jm_id}")
                if _is_restricted(album_resp):
                    raise ValueError(f"禁漫车号 JM{jm_id} 受权限保护（需登录查看），当前账号无权访问或登录会话已失效")
            else:
                raise ValueError(
                    f"禁漫车号 JM{jm_id} 受权限保护（需登录查看），请在 .env 中配置 JM_USERNAME 与 JM_PASSWORD 后重试"
                )

        if (
            "album_missing" in getattr(album_resp, "url", "")
            or "album_missing" in album_resp.text
            or "/error/" in getattr(album_resp, "url", "")
        ):
            raise ValueError(f"禁漫车号 JM{jm_id} 不存在或已被下架")

        try:
            detail = JmcomicText.analyse_jm_album_html(album_resp.text)
        except Exception as exc:
            if "album_id" in str(exc) or "pattern_html_album_" in str(exc):
                raise ValueError(f"禁漫车号 JM{jm_id} 页面解析失败（可能不存在或已被删除）") from exc
            raise
        uploader = self._parse_uploader(album_resp.text)

        def fetch_photo_html(pid: str):
            nonlocal client
            photo_resp = client.get(f"/photo/{pid}")
            if _is_restricted(photo_resp):
                if JM_USERNAME and JM_PASSWORD:
                    logger.info("检测到单话 %s 受限，尝试 HTML 会话重登并重试...", pid)
                    self._clear_session_cache()
                    client = self._make_html_client(force_refresh_session=True)
                    photo_resp = client.get(f"/photo/{pid}")
                else:
                    raise ValueError(
                        f"禁漫话数 {pid} 受权限保护（需登录查看），请在 .env 中配置 JM_USERNAME 与 JM_PASSWORD 后重试"
                    )
                if _is_restricted(photo_resp):
                    raise ValueError(f"禁漫话数 {pid} 需登录后才能查看，当前账号无权访问或登录会话已失效")
            photo = JmcomicText.analyse_jm_photo_html(photo_resp.text)
            photo.from_album = detail
            return photo

        return self._assemble_fetched_comic(
            jm_id=jm_id,
            detail=detail,
            fetch_photo=fetch_photo_html,
            existing=existing,
            uploader=uploader,
            source_url=str(album_resp.url),
        )

    def _assemble_fetched_comic(
        self,
        jm_id: str,
        detail,
        fetch_photo,
        existing: FetchedComic | None = None,
        uploader: str | None = None,
        source_url: str = "",
    ) -> FetchedComic:
        episodes = [
            (ep[0], (ep[2] if len(ep) > 2 else "").strip())
            for ep in (detail.episode_list or [])
        ]
        if not episodes:
            episodes = [(jm_id, "")]

        multi = len(episodes) > 1

        existing_chapter_map = {
            c.id: c for c in (existing.meta.chapters if existing else [])
        }
        existing_pages_by_chap: dict[str, list[RemotePage]] = {}
        if existing:
            for p in existing.remote_pages:
                if p.chapter:
                    existing_pages_by_chap.setdefault(p.chapter, []).append(p)
                elif not existing.meta.chapters and len(episodes) > 1:
                    first_pid = episodes[0][0]
                    existing_pages_by_chap.setdefault(first_pid, []).append(p)

        api_has_page_count = int(detail.page_count or 0) > 0
        all_ids_match = (
            existing is not None
            and multi
            and [c.id for c in existing.meta.chapters] == [ep[0] for ep in episodes]
            and (
                existing.meta.page_count == int(detail.page_count or 0)
                if api_has_page_count
                else True
            )
        )
        single_match = (
            existing is not None
            and not multi
            and not existing.meta.chapters
            and (
                existing.meta.page_count == int(detail.page_count or 0)
                if api_has_page_count
                else True
            )
        )

        remote_pages: list[RemotePage] = []
        chapters: list[Chapter] = []
        first_photo = None

        now = datetime.now(timezone.utc).isoformat()

        if all_ids_match or single_match:
            remote_pages = [
                RemotePage.model_validate(p.model_dump()) for p in existing.remote_pages
            ]
            for i, page in enumerate(remote_pages, start=1):
                page.index = i
            chapters = [
                Chapter.model_validate(c.model_dump()) for c in existing.meta.chapters
            ]
            page_count = len(remote_pages) or int(detail.page_count or 0)
            image_domain = str((existing.meta.raw or {}).get("image_domain", "") or "")
        else:
            def _fetch_episode(pid: str, ptitle: str, ordinal: int):
                nonlocal first_photo
                photo = fetch_photo(pid)
                if getattr(photo, "data_original_0", None):
                    photo.data_original_query_params = photo.get_data_original_query_params(
                        photo.data_original_0
                    )
                if first_photo is None:
                    first_photo = photo

                ep_pages: list[RemotePage] = []
                for index in range(len(photo.page_arr)):
                    image = photo.create_image_detail(index)
                    filename = f"{index + 1:05d}{image.img_file_suffix}"
                    ep_pages.append(
                        RemotePage(
                            index=0,
                            url=image.download_url,
                            file=filename,
                            ext=image.img_file_suffix,
                            scramble_id=str(photo.scramble_id or ""),
                            chapter=pid if multi else "",
                            headers={
                                "Referer": source_url or f"https://18comic.vip/album/{jm_id}",
                                "User-Agent": (
                                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                                    "Chrome/124.0 Safari/537.36"
                                ),
                            },
                        )
                    )
                chap_title = ptitle or str(getattr(photo, "name", None) or f"第 {ordinal} 話")
                return ep_pages, chap_title

            def _append_episode(ep_pages: list[RemotePage], pid: str, chap_title: str, ordinal: int) -> None:
                start = len(remote_pages) + 1
                for p in ep_pages:
                    p.index = len(remote_pages) + 1
                    remote_pages.append(p)
                if multi:
                    chapters.append(
                        Chapter(
                            id=pid,
                            index=ordinal,
                            title=chap_title,
                            page_count=len(ep_pages),
                            start=start,
                        )
                    )

            def _pull_all_episodes() -> None:
                nonlocal remote_pages, chapters, first_photo
                remote_pages = []
                chapters = []
                first_photo = None
                for ord_idx, (p_id, p_title) in enumerate(episodes, start=1):
                    e_pages, c_title = _fetch_episode(p_id, p_title, ord_idx)
                    _append_episode(e_pages, p_id, c_title, ord_idx)

            for ordinal, (pid, ptitle) in enumerate(episodes, start=1):
                cached_pages = existing_pages_by_chap.get(pid)
                cached_chap = existing_chapter_map.get(pid)

                if cached_pages and (
                    cached_chap is not None
                    or (existing and not existing.meta.chapters and ordinal == 1)
                ):
                    copied = [RemotePage.model_validate(p.model_dump()) for p in cached_pages]
                    for p in copied:
                        p.chapter = pid if multi else ""
                    chap_title = ptitle or (
                        cached_chap.title if cached_chap else f"第 {ordinal} 話"
                    )
                    _append_episode(copied, pid, chap_title, ordinal)
                else:
                    ep_pages, chap_title = _fetch_episode(pid, ptitle, ordinal)
                    _append_episode(ep_pages, pid, chap_title, ordinal)

            expected_total = int(detail.page_count or 0)
            if expected_total > 0 and len(remote_pages) != expected_total and existing is not None:
                _pull_all_episodes()

            page_count = len(remote_pages) or int(detail.page_count or 0)
            image_domain = (
                getattr(first_photo, "data_original_domain", "")
                if first_photo
                else str((existing.meta.raw or {}).get("image_domain", "") or "")
                if existing
                else ""
            )

        # 清洗 API 模式下被硬编码为 '0' 或 None 的字段，优先继承已有元数据
        raw_pub_date = str(getattr(detail, "pub_date", "") or "").strip()
        pub_date = (
            raw_pub_date
            if raw_pub_date and raw_pub_date != "0"
            else (existing.meta.published_at if existing else "")
        )
        raw_update_date = str(getattr(detail, "update_date", "") or "").strip()
        update_date = (
            raw_update_date
            if raw_update_date and raw_update_date != "0"
            else (existing.meta.updated_at if existing else "")
        )
        effective_uploader = uploader or (existing.meta.uploader if existing else None)

        meta = ComicMeta(
            source=self.key,
            source_id=jm_id,
            display_id=f"JM{jm_id}",
            title=str(getattr(detail, "name", "") or getattr(detail, "title", "") or ""),
            authors=list(getattr(detail, "authors", []) or []),
            works=list(getattr(detail, "works", []) or []),
            actors=list(getattr(detail, "actors", []) or []),
            tags=list(getattr(detail, "tags", []) or []),
            description=str(getattr(detail, "description", "") or ""),
            uploader=effective_uploader,
            page_count=page_count,
            published_at=pub_date,
            updated_at=update_date,
            views=format_count(getattr(detail, "views", "") or ""),
            likes=format_count(getattr(detail, "likes", "") or ""),
            comment_count=int(getattr(detail, "comment_count", 0) or 0),
            cover_count=min(COVER_COUNT, page_count) if page_count else COVER_COUNT,
            source_url=source_url or f"https://18comic.vip/album/{jm_id}",
            pages=[
                {
                    "index": page.index,
                    "file": page.file,
                    "ext": page.ext,
                    "cached": False,
                    "chapter": page.chapter,
                }
                for page in remote_pages
            ],
            chapters=chapters,
            imported_at=now,
            last_checked_at=now,
            raw={
                "album": {
                    k: v
                    for k, v in detail.__dict__.items()
                    if not k.startswith("_")
                },
                "uploader": uploader,
                "image_domain": image_domain,
                "chapters": [c.model_dump() for c in chapters],
            },
        )

        return FetchedComic(meta=meta, remote_pages=remote_pages)

    def fetch(
        self,
        raw_id: str,
        *,
        existing: FetchedComic | None = None,
    ) -> FetchedComic:
        jm_id = self.normalize_id(raw_id)

        # 1. 优先使用 API 客户端（针对受限画卷天然适配 AVS 凭据，无网页 CAPTCHA 与 album_missing 假拦截）
        try:
            return self._fetch_via_api(jm_id, existing=existing)
        except (ValueError, RuntimeError) as exc:
            # 若是明确的权限/账号配置错误，直接上浮明确提示，不再做无意义的 HTML 重试
            if "受权限保护" in str(exc) or "需登录查看" in str(exc):
                raise
            logger.warning("禁漫 API 客户端解析车号 JM%s 失败: %s，尝试降级到 HTML 网页解析...", jm_id, _mask_sensitive(exc))
        except Exception as exc:
            logger.warning("禁漫 API 客户端解析车号 JM%s 异常: %s，尝试降级到 HTML 网页解析...", jm_id, _mask_sensitive(exc))

        # 2. 降级到既有的 HTML 网页客户端解析
        return self._fetch_via_html(jm_id, existing=existing)

    @staticmethod
    def _is_image_bytes(content: bytes) -> bool:
        """Verify binary magic bytes for JPEG, PNG, WebP, GIF, or AVIF.

        Prevents upstream WAF / CDN challenge HTML pages (often returned as HTTP 200)
        from corrupting the image cache (PITFALLS.md #60).
        """
        if len(content) < 16:
            return False
        # JPEG
        if content.startswith(b"\xff\xd8\xff"):
            return True
        # PNG
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return True
        # WebP: RIFF....WEBP
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return True
        # GIF
        if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
            return True
        # AVIF
        if b"ftypavif" in content[:32] or b"ftypavis" in content[:32]:
            return True
        return False

    # One session per thread + connection pooling. Creating a brand new session
    # per page was the biggest cost: each one did a fresh TLS handshake, and any
    # flaky image made the whole (pre)fetch appear to hang for tens of seconds.
    _tls = threading.local()

    def _session(self):
        session = getattr(self._tls, "session", None)
        proxies = self._get_image_proxies()
        if session is None:
            session = curl_requests.Session(impersonate="chrome")
            if proxies:
                session.proxies = proxies
            self._tls.session = session
        else:
            session.proxies = proxies or {}
        return session

    @staticmethod
    def _cache_bust(url: str, attempt: int) -> str:
        """Add a fresh query param so a sticky CDN error can be dodged."""
        marker = f"_r={int(time.time())}{attempt}"
        if "?" in url:
            return f"{url}&{marker}"
        return f"{url}?{marker}"

    def download_page(self, comic: FetchedComic, page: RemotePage) -> bytes:
        # Cap in-flight image requests globally: the detail page asks for many
        # thumbnails at once and JM's CDN throttles/queues parallel bursts so
        # every simultaneous request times out. A small steady pool keeps each
        # download fast while still letting pages download concurrently.
        with download_gate:
            return self._do_download(comic, page)

    def _do_download(self, comic: FetchedComic, page: RemotePage) -> bytes:
        from jmcomic import JmModuleConfig

        session = self._session()
        headers = dict(page.headers)
        headers.setdefault("Accept", "image/avif,image/webp,image/apng,image/*,*/*;q=0.8")

        parsed_url = urlparse(page.url)
        orig_domain = parsed_url.hostname or ""

        # 构建包含官方多 CDN 集群的容灾候选池 (Multi-CDN Failover)，严格过滤内网与不安全主机
        cdn_candidates: list[str] = [orig_domain] if orig_domain and _is_safe_remote_domain(orig_domain) else []
        for cand in JmModuleConfig.DOMAIN_IMAGE_LIST:
            if cand and _is_safe_remote_domain(cand) and cand not in cdn_candidates:
                cdn_candidates.append(cand)
        if not cdn_candidates:
            raise RuntimeError(
                f"未找到可信安全的图片 CDN 域名（原始域名受限或已被阻断: {orig_domain}）"
            )

        transient = {401, 403, 429, 500, 502, 503, 504}
        last_err: RuntimeError | None = None
        max_attempts = max(4, min(len(cdn_candidates), 6))

        for attempt in range(max_attempts):
            curr_domain = cdn_candidates[attempt % len(cdn_candidates)]
            target_url = parsed_url._replace(netloc=curr_domain, scheme="https").geturl()
            url = target_url if attempt == 0 else self._cache_bust(target_url, attempt)

            try:
                resp = session.get(url, headers=headers, timeout=35, allow_redirects=True)
            except Exception as exc:
                safe_exc = _mask_sensitive(exc)
                last_err = RuntimeError(
                    f"下载图片失败 {comic.meta.display_id} 第{page.index}页 ({curr_domain}): {safe_exc}"
                )
                time.sleep(0.3 * (attempt + 1))
                continue

            if resp.status_code == 200:
                if not self._is_image_bytes(resp.content):
                    last_err = RuntimeError(
                        f"下载图片异常 {comic.meta.display_id} 第{page.index}页 ({curr_domain}): "
                        f"收到非图像内容 (长度 {len(resp.content)}B，可能为上游 CDN/WAF 拦截页)"
                    )
                    time.sleep(0.3 * (attempt + 1))
                    continue
                return self._decode_page(page, resp.content)

            if resp.status_code in transient:
                last_err = RuntimeError(
                    f"下载图片失败 {comic.meta.display_id} 第{page.index}页 ({curr_domain}): "
                    f"HTTP {resp.status_code}"
                )
                time.sleep(0.3 * (attempt + 1))
                continue

            last_err = RuntimeError(
                f"下载图片失败 {comic.meta.display_id} 第{page.index}页 ({curr_domain}): "
                f"HTTP {resp.status_code}"
            )
            time.sleep(0.3 * (attempt + 1))

        raise last_err or RuntimeError(
            f"下载图片失败 {comic.meta.display_id} 第{page.index}页: 未知错误"
        )

    @staticmethod
    def _decode_page(page: RemotePage, raw: bytes) -> bytes:
        """Apply jmcomic's official JM image de-scramble algorithm.

        The page is downloaded raw and then decoded with ``JmImageTool``, the
        exact routine used by ``JmDownloader`` / ``download_image``.
        """
        from jmcomic import JmImageTool

        if not page.scramble_id:
            return raw

        url = page.url.split("?", 1)[0]
        try:
            num = JmImageTool.get_num_by_url(page.scramble_id, url)
        except Exception as exc:
            logger.warning("解析图片分割数异常 (%s, %s): %s，回退为原图", page.scramble_id, url, exc)
            return raw
        if num == 0:
            return raw

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / f"decoded{page.ext or '.webp'}"
            source = JmImageTool.open_image(raw)
            try:
                JmImageTool.decode_and_save(num, source, str(tmp_path))
            finally:
                source.close()
            return tmp_path.read_bytes()

    def fetch_ranking(
        self, timeframe: str = "week", page: int = 1, limit: int = 20
    ) -> list[DiscoveryItem]:
        from jmcomic import JmModuleConfig, JmOption

        JmModuleConfig.FLAG_ENABLE_JM_LOG = False
        option = JmOption.default()
        control_proxies = self._get_control_proxies()
        option.client.postman.meta_data["proxies"] = control_proxies
        cookies = self._get_valid_cookies(option)
        if cookies:
            option.update_cookies(cookies)

        client = option.build_jm_client()

        if timeframe == "day":
            resp = client.day_ranking(page=page)
        elif timeframe == "month":
            resp = client.month_ranking(page=page)
        else:
            resp = client.week_ranking(page=page)

        try:
            ranking_domain = self.resolve_html_domain()
        except Exception:
            ranking_domain = "18comic.vip"

        items: list[DiscoveryItem] = []
        if hasattr(resp, "content") and resp.content:
            raw_list = resp.content[:limit] if limit > 0 else resp.content
            for item in raw_list:
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict):
                    data = item[1]
                    aid = str(data.get("id") or item[0])
                    name = str(data.get("name") or "")
                    author = str(data.get("author") or "")
                    cat_info = data.get("category")
                    category = ""
                    if isinstance(cat_info, dict):
                        category = str(cat_info.get("title") or "")
                    elif isinstance(cat_info, str):
                        category = cat_info

                    items.append(
                        DiscoveryItem(
                            id=f"JM{aid}",
                            source_id=aid,
                            source="jm",
                            title=name,
                            author=author,
                            category=category,
                            url=f"https://{ranking_domain}/album/{aid}",
                        )
                    )
        return items

