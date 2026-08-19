from __future__ import annotations

import html as html_lib
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
import threading
from urllib.parse import urlparse

from curl_cffi import requests as curl_requests

from ..config import COVER_COUNT, DATA_DIR
from ..gate import download_gate
from ..models import Chapter, ComicMeta, FetchedComic, RemotePage
from .base import ComicProvider

_JM_REDIRECT_URL = "https://jm365.work/3YeBdF"
_FALLBACK_HTML_DOMAINS = [
    "comic18j-rita.cc",
    "18comic.vip",
    "18comic.org",
    "jmcomic1.me",
]
_DOMAIN_TTL_SECONDS = 6 * 60 * 60


class JMProvider(ComicProvider):
    """禁漫天堂 provider.

    Metadata comes from the HTML album page (it contains the uploader,
    dates, formatted views/likes and the real photo image URL list).
    """

    key = "jm"
    label = "禁漫天堂 (JMComic)"
    short_label = "禁漫"
    id_pattern = r"^(?:JM)?(\d{6,8})$"
    example = "JM523607"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._domain_cache_file = DATA_DIR / "jm_html_domain.json"

    # ------------------------------------------------------------------
    # id / domain helpers
    # ------------------------------------------------------------------
    def normalize_id(self, raw: str) -> str:
        m = re.fullmatch(self.id_pattern, raw.strip())
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

            session = curl_requests.Session(impersonate="chrome")
            domain = ""
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
                domain = parsed.hostname or ""
                if not domain or domain in {"jm-88.cc"}:
                    domain = ""
            except Exception:
                domain = ""

            if not domain:
                for candidate in _FALLBACK_HTML_DOMAINS:
                    try:
                        probe = session.get(
                            f"https://{candidate}/",
                            timeout=8,
                            allow_redirects=True,
                        )
                        if probe.status_code == 200 and len(probe.content) > 1000:
                            domain = urlparse(str(probe.url)).hostname or candidate
                            break
                    except Exception:
                        continue

            if not domain:
                raise RuntimeError("无法找到可用的禁漫网页域名，请稍后重试")

            self._write_html_domain(domain)
            return domain

    # ------------------------------------------------------------------
    # fetching
    # ------------------------------------------------------------------
    def _make_html_client(self):
        from jmcomic import JmModuleConfig, JmOption

        JmModuleConfig.FLAG_ENABLE_JM_LOG = False
        option = JmOption.default()
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

    def fetch(self, raw_id: str) -> FetchedComic:
        from jmcomic import JmcomicText

        jm_id = self.normalize_id(raw_id)
        client = self._make_html_client()

        album_resp = client.get(f"/album/{jm_id}")
        detail = JmcomicText.analyse_jm_album_html(album_resp.text)
        uploader = self._parse_uploader(album_resp.text)

        # Each album carries one or more chapters (episodes). A single-chapter
        # album's episode_list is [(album_id, "1", name)], so fetching each
        # episode by its own photo id stays backward compatible.
        episodes = [
            (ep[0], ep[2] if len(ep) > 2 else "")
            for ep in (detail.episode_list or [])
        ]
        if not episodes:
            episodes = [(jm_id, "")]

        multi = len(episodes) > 1

        # Flatten every chapter's pages with global 1-based indexes, so the
        # whole multi-chapter album remains addressable as one list — reader
        # page numbers, covers and "继续阅读" all stay global. Multi-chapter
        # pages carry their chapter id so storage can route them into
        # per-chapter subdirectories.
        remote_pages: list[RemotePage] = []
        chapters: list[Chapter] = []
        first_photo = None

        for ordinal, (pid, ptitle) in enumerate(episodes, start=1):
            photo_resp = client.get(f"/photo/{pid}")
            photo = JmcomicText.analyse_jm_photo_html(photo_resp.text)
            photo.from_album = detail
            photo.data_original_query_params = photo.get_data_original_query_params(
                photo.data_original_0
            )
            if first_photo is None:
                first_photo = photo

            start = len(remote_pages) + 1
            for index in range(len(photo.page_arr)):
                image = photo.create_image_detail(index)
                filename = f"{index + 1:05d}{image.img_file_suffix}"
                remote_pages.append(
                    RemotePage(
                        index=len(remote_pages) + 1,
                        url=image.download_url,
                        file=filename,
                        ext=image.img_file_suffix,
                        scramble_id=str(photo.scramble_id or ""),
                        chapter=pid if multi else "",
                        headers={
                            "Referer": (
                                f"https://{urlparse(str(photo_resp.url)).hostname or ''}"
                                f"/photo/{pid}"
                            ),
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0 Safari/537.36"
                            ),
                        },
                    )
                )

            if multi:
                chapters.append(
                    Chapter(
                        id=pid,
                        index=ordinal,
                        title=ptitle or str(photo.name or f"第 {ordinal} 話"),
                        page_count=len(photo.page_arr),
                        start=start,
                    )
                )

        now = datetime.now(timezone.utc).isoformat()
        page_count = len(remote_pages) or int(detail.page_count or 0)

        meta = ComicMeta(
            source=self.key,
            source_id=jm_id,
            display_id=f"JM{jm_id}",
            title=detail.name,
            authors=list(detail.authors),
            works=list(detail.works),
            actors=list(detail.actors),
            tags=list(detail.tags),
            description=detail.description or "",
            uploader=uploader,
            page_count=page_count,
            published_at=str(detail.pub_date or ""),
            updated_at=str(detail.update_date or ""),
            views=str(detail.views or ""),
            likes=str(detail.likes or ""),
            comment_count=int(detail.comment_count or 0),
            cover_count=min(COVER_COUNT, page_count) if page_count else COVER_COUNT,
            source_url=str(album_resp.url),
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
            imported_at=now,
            last_checked_at=now,
            raw={
                "album": {
                    k: v
                    for k, v in detail.__dict__.items()
                    if not k.startswith("_")
                },
                "uploader": uploader,
                "image_domain": first_photo.data_original_domain if first_photo else "",
                "chapters": [c.model_dump() for c in chapters],
            },
        )

        return FetchedComic(meta=meta, remote_pages=remote_pages)

    # One session per thread + connection pooling. Creating a brand new session
    # per page was the biggest cost: each one did a fresh TLS handshake, and any
    # flaky image made the whole (pre)fetch appear to hang for tens of seconds.
    _tls = threading.local()

    def _session(self):
        session = getattr(self._tls, "session", None)
        if session is None:
            session = curl_requests.Session(impersonate="chrome")
            self._tls.session = session
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
        session = self._session()
        headers = dict(page.headers)
        headers.setdefault("Accept", "image/avif,image/webp,image/apng,image/*,*/*;q=0.8")

        transient = {401, 403, 429, 500, 502, 503, 504}
        last_err: RuntimeError | None = None
        for attempt in range(4):
            url = page.url if attempt == 0 else self._cache_bust(page.url, attempt)
            try:
                resp = session.get(url, headers=headers, timeout=45, allow_redirects=True)
            except Exception as exc:
                last_err = RuntimeError(
                    f"下载图片失败 {comic.meta.display_id} 第{page.index}页: {exc}"
                )
                time.sleep(0.5 * (attempt + 1))
                continue

            if resp.status_code == 200:
                if len(resp.content) < 100:
                    last_err = RuntimeError(
                        f"下载图片异常 {comic.meta.display_id} 第{page.index}页: 内容过短"
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return self._decode_page(page, resp.content)

            if resp.status_code in transient:
                last_err = RuntimeError(
                    f"下载图片失败 {comic.meta.display_id} 第{page.index}页: "
                    f"HTTP {resp.status_code}"
                )
                time.sleep(0.5 * (attempt + 1))
                continue

            raise RuntimeError(
                f"下载图片失败 {comic.meta.display_id} 第{page.index}页: "
                f"HTTP {resp.status_code}"
            )

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
        num = JmImageTool.get_num_by_url(page.scramble_id, url)
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
