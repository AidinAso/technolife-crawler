from urllib.parse import (
    urljoin,
    urlsplit,
    urlunsplit,
    urldefrag
)
import posixpath


class URLChecker:

    def __init__(self, allowed_domain):
        self.allowed_domain = allowed_domain.lower()
        self.seen_urls = set()


    def normalize(self, url, base_url=None):

        if base_url:
            url = urljoin(base_url, url)

        url, _ = urldefrag(url)

        try:
            parts = urlsplit(url)

            scheme = parts.scheme.lower()
            hostname = (parts.hostname or "").lower()

            if scheme not in ("http", "https"):
                return None

            if not hostname:
                return None

            if parts.username or parts.password:
                return None

            port = parts.port

            netloc = hostname

            if port is not None and not (
                (scheme == "http" and port == 80)
                or (scheme == "https" and port == 443)
            ):
                netloc += f":{port}"

            path = parts.path or "/"

            had_trailing_slash = path.endswith("/")
            path = posixpath.normpath(path)

            if not path.startswith("/"):
                path = "/" + path

            if had_trailing_slash and not path.endswith("/"):
                path += "/"

            query = parts.query

            return urlunsplit((
                scheme,
                netloc,
                path,
                query,
                ""
            ))

        except ValueError:
            return None

    def is_allowed_domain(self, url):

        hostname = urlsplit(url).hostname

        if not hostname:
            return False

        return (
            hostname == self.allowed_domain
            or hostname.endswith("." + self.allowed_domain)
        )

    def is_html_candidate(self, url):

        excluded_extensions = (
            ".jpg", ".jpeg", ".png", ".gif",
            ".webp", ".svg", ".pdf", ".zip",
            ".rar", ".mp4", ".mp3", ".css",
            ".js", ".woff", ".woff2", ".ico"
        )

        path = urlsplit(url).path.lower()

        return not path.endswith(excluded_extensions)

    def check(self, url, base_url=None):

        normalized_url = self.normalize(url, base_url)

        if normalized_url is None:
            return None

        if not self.is_allowed_domain(normalized_url):
            return None

        if not self.is_html_candidate(normalized_url):
            return None

        if normalized_url in self.seen_urls:
            return None

        self.seen_urls.add(normalized_url)

        return normalized_url