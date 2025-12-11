from django import template
from urllib.parse import urlparse, parse_qs

register = template.Library()

def _yt_id(url: str) -> str:
    if not url:
        return ""
    u = urlparse(url)
    host = (u.netloc or "").lower()

    # youtu.be/<ID>
    if host.endswith("youtu.be"):
        return u.path.lstrip("/")

    # youtube.com/watch?v=<ID> | /shorts/<ID> | /embed/<ID>
    if "youtube.com" in host:
        if u.path.startswith("/watch"):
            return parse_qs(u.query).get("v", [""])[0]
        if u.path.startswith("/shorts/"):
            return u.path.split("/shorts/")[-1]
        if u.path.startswith("/embed/"):
            return u.path.split("/embed/")[-1]
    return ""

@register.filter
def youtube_id(url: str) -> str:
    return _yt_id(url)

@register.filter
def youtube_embed(url: str) -> str:
    vid = _yt_id(url)
    return f"https://www.youtube.com/embed/{vid}" if vid else ""
