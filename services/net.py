"""Скачивание с пределом размера и проверка адресов из чужих ответов.

Без предела сервер (или подменённый ответ в чужой Wi-Fi) мог отдать сотни мегабайт вместо картинки
или записи радио — всё читалось в память целиком (аудит, SEC-3). Адреса фото приходят из ответа OpenF1:
скачиваем только https с известных хостов (SEC-6).
"""
from urllib.parse import urlsplit

import requests

CHUNK = 1 << 16


class TooLarge(requests.RequestException):
    """Ответ больше допустимого — дочитывать не стали."""


def allowed(url, hosts):
    """https и хост из списка (или его поддомен)."""
    try:
        parts = urlsplit(str(url))
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in hosts)


def get_limited(get, url, limit, **kw):
    """get — requests.get или Session.get. Читает ответ частями и бросает TooLarge, как только он
    превысил limit байт. -> (код ответа, байты)."""
    resp = get(url, stream=True, **kw)
    try:
        declared = resp.headers.get("Content-Length") if getattr(resp, "headers", None) else None
        if declared and str(declared).isdigit() and int(declared) > limit:
            raise TooLarge(f"{url}: {declared} байт > {limit}")
        data = bytearray()
        for chunk in resp.iter_content(CHUNK):
            data += chunk
            if len(data) > limit:
                raise TooLarge(f"{url}: больше {limit} байт")
        return resp.status_code, bytes(data)
    finally:
        close = getattr(resp, "close", None)
        if close:
            close()
