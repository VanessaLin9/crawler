from __future__ import annotations

from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(slots=True)
class FetchSession:
    user_agent: str


@dataclass(slots=True)
class FetchResponse:
    status_code: int
    text: str


def build_session(user_agent: str) -> FetchSession:
    return FetchSession(user_agent=user_agent)


def fetch_html(
    session: FetchSession,
    url: str,
    timeout: float,
) -> FetchResponse:
    request = Request(url, headers={"User-Agent": session.user_agent})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
        return FetchResponse(status_code=response.getcode(), text=body)
