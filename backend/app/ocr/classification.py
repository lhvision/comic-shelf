"""台词索引的保守分类：明确广告按页排除，普通词、英文短句和重复对白保持可检索。

分类只影响派生索引，不改写画页旁的 OCR 伴生资产。广告、制作说明及后记保存为
paratext；页码和明确的平台水印不参与索引。页面位置和重复频率本身不构成广告证据。
"""

from __future__ import annotations

import re
from typing import Any

from ..zh_conv import to_simplified

DIALOGUE_KIND = "dialogue"
PARATEXT_KIND = "paratext"
CLASSIFICATION_VERSION = 3

_PLATFORM_RE = re.compile(r"禁漫(?:天堂|食堂|娘)|拷贝漫画|jm(?:官方|comic)|18comic", re.IGNORECASE)
_DOWNLOAD_RE = re.compile(r"扫码(?:下载|安装)|扫描(?:二维码|\s*qrcode)|app(?:下载|正式启动)|官方下载", re.IGNORECASE)
_QR_RE = re.compile(r"扫描(?:二维码|\s*qrcode)|扫码下载", re.IGNORECASE)
_LINK_RE = re.compile(r"https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:com|net|org|work|xyz)\b", re.IGNORECASE)
_RECRUIT_RE = re.compile(r"(?:汉化组|翻译组|制作组).{0,12}(?:招募|招新|诚聘)|(?:诚聘|招募).{0,8}(?:嵌字|初翻)")
_CONTACT_RE = re.compile(r"(?:qq|微信|交流)群\s*[:：]|群号\s*[:：]|邮箱\s*[:：]|@[a-z0-9_]+", re.IGNORECASE)
_CREDIT_RE = re.compile(
    r"(?:图源|翻校|嵌字|扫图|校对|压制|汉化|翻译|初翻)\s*[:：]"
    r"|(?:个人汉化|汉化组制作|汉化组诚聘|汉化组招募)|仅供交流|禁止商用|严禁商用",
    re.IGNORECASE,
)
_PARATEXT_RE = re.compile(
    r"^(?:作者)?(?:后记|前言|版权|制作名单)|^\s*(?:pixiv\s*id|邮箱|群号|qq群)\s*[:：]"
    r"|^presented\s+by\b|^\s*\S*@[a-z0-9_]+\s*$",
    re.IGNORECASE,
)
_WATERMARK_RE = re.compile(r"(?:jmcomic|mcomic|imcomic|nenic|r18|禁漫天堂|禁漫食堂|禁漫娘|拷贝漫画)", re.IGNORECASE)


def is_noise_line(text: str) -> bool:
    """只移除明确页码、站点水印和空白，不根据字母或短句长度否定对白。"""
    clean = to_simplified(text).strip()
    return not clean or re.fullmatch(r"\d{1,4}|\.{3,}", clean) is not None or _WATERMARK_RE.fullmatch(clean) is not None


def advertisement_page_reason(page_texts: list[str], bubbles: list[dict[str, Any]] | None = None) -> str:
    """组合独立广告证据；有坐标时要求广告信息覆盖页面，防止角落水印连累正文。

    平台、下载引导和地址同时出现，或明确汉化招聘与联系方式同时出现，才候选整页广告。
    至少两个气泡提供证据；有合法坐标时，证据框总面积须达到页面的 12%。无坐标历史
    资产只能依靠文字证据，仍不使用页码位置、重复次数或普通营销词判定。
    """
    texts = [to_simplified(text).strip() for text in page_texts]
    joined = "\n".join(texts)
    platform = bool(_PLATFORM_RE.search(joined))
    download = bool(_DOWNLOAD_RE.search(joined))
    link = bool(_LINK_RE.search(joined))
    recruitment = bool(_RECRUIT_RE.search(joined))
    contact = bool(_CONTACT_RE.search(joined))
    reason = "platform_download_poster" if platform and download and (link or _QR_RE.search(joined)) else ""
    if recruitment and contact:
        reason = reason or "scanlator_recruitment_poster"
    if not reason:
        return ""
    patterns = (_PLATFORM_RE, _DOWNLOAD_RE, _LINK_RE, _RECRUIT_RE, _CONTACT_RE)
    anchors = [index for index, text in enumerate(texts) if any(pattern.search(text) for pattern in patterns)]
    if len(anchors) < 2:
        return ""
    if bubbles is not None:
        area = 0.0
        valid_boxes = 0
        for index in anchors:
            box = bubbles[index].get("box")
            if not isinstance(box, list) or len(box) != 4:
                continue
            if not all(
                isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1 for value in box
            ):
                continue
            ymin, xmin, ymax, xmax = box
            valid_boxes += 1
            area += max(0, ymax - ymin) * max(0, xmax - xmin)
        if valid_boxes and area < 0.12:
            return ""
    return reason


def classify_dialogue_kind(text: str, *, is_advertisement: bool = False) -> str | None:
    """明确副文本才排除检索；页码、长度和重复频率不再作为分类输入。"""
    if is_noise_line(text):
        return None
    norm_text = to_simplified(text).strip()
    if is_advertisement or _CREDIT_RE.search(norm_text) or _PARATEXT_RE.search(norm_text):
        return PARATEXT_KIND
    if (
        _LINK_RE.fullmatch(norm_text)
        or _RECRUIT_RE.search(norm_text)
        or _PLATFORM_RE.search(norm_text)
        and _DOWNLOAD_RE.search(norm_text)
    ):
        return PARATEXT_KIND
    return DIALOGUE_KIND
