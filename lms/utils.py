from urllib.parse import urlparse, parse_qs

def youtube_to_embed(url: str) -> str:
    """Convierte enlaces de YouTube (watch, shorts, youtu.be) a /embed/<id>.
    Si no reconoce el formato, devuelve el mismo URL.
    """
    if not url:
        return url
    url = url.strip()

    # shorts
    if "shorts/" in url:
        vid = url.split("shorts/")[-1].split("?")[0]
        return f"https://www.youtube.com/embed/{vid}"

    # youtu.be/<id>
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[-1].split("?")[0]
        return f"https://www.youtube.com/embed/{vid}"

    # youtube.com/watch?v=<id>
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return f"https://www.youtube.com/embed/{qs['v'][0]}"

    return url
