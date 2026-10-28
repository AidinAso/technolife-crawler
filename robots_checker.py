import requests
from protego import Protego
from urllib.parse import urlsplit


class RobotsChecker:

    def __init__(self, user_agent="EducationalCrawler/1.0", on_warning=None):
        self.user_agent = user_agent
        self.on_warning = on_warning
        self.parsers = {}

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent
        })

    def _warn(self, message):

        if self.on_warning is not None:
            self.on_warning(message)
        else:
            print(message)

    def is_allowed(self, url):

        parts = urlsplit(url)

        if parts.scheme not in ("http", "https"):
            return False

        base_url = f"{parts.scheme}://{parts.netloc}"

        if base_url not in self.parsers:

            robots_url = base_url + "/robots.txt"

            try:
                response = self.session.get(
                    robots_url,
                    timeout=15,
                    allow_redirects=True
                )

                if response.status_code != 200:
                    self._warn(
                        f"Cannot verify robots.txt (HTTP {response.status_code})"
                    )
                    return False

                content_type = response.headers.get(
                    "Content-Type", ""
                ).lower()

                if "text/plain" not in content_type:
                    self._warn("Invalid robots.txt content type")
                    return False

                parser = Protego.parse(response.text)

                self.parsers[base_url] = parser

            except requests.exceptions.RequestException as error:
                self._warn(f"Robots error: {error}")
                return False

            finally:
                if "response" in locals():
                    response.close()
                    
        return self.parsers[base_url].can_fetch(
            url,
            self.user_agent
        )

    def close(self):
        self.session.close()
