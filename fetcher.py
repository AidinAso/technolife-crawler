import requests
import time


class Fetcher:

    def __init__(self, timeout=10, max_size=5 * 1024 * 1024):

        self.timeout = timeout
        self.max_size = max_size

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "EducationalCrawler/1.0"
        })

    def fetch(self, url):

        start_time = time.perf_counter()

        try:
            with self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True
            ) as response:

                status_code = response.status_code

                if status_code in (301, 302, 303, 307, 308):

                    return {
                        "success": False,
                        "redirect": True,
                        "url": url,
                        "location": response.headers.get("Location"),
                        "status_code": status_code,
                        "elapsed_time": time.perf_counter() - start_time
                    }

                if status_code != 200:

                    return {
                        "success": False,
                        "redirect": False,
                        "url": url,
                        "status_code": status_code,
                        "error": f"HTTP {status_code}",
                        "elapsed_time": time.perf_counter() - start_time
                    }

                content_type = response.headers.get(
                    "Content-Type", ""
                ).lower()

                if "text/html" not in content_type:

                    return {
                        "success": False,
                        "redirect": False,
                        "url": url,
                        "status_code": status_code,
                        "error": "Not an HTML page",
                        "elapsed_time": time.perf_counter() - start_time
                    }

                content_length = response.headers.get(
                    "Content-Length"
                )

                if content_length is not None:

                    try:
                        if int(content_length) > self.max_size:

                            return {
                                "success": False,
                                "redirect": False,
                                "url": url,
                                "status_code": status_code,
                                "error": "HTML page exceeds maximum size",
                                "elapsed_time": time.perf_counter() - start_time
                            }

                    except ValueError:
                        pass

                content = bytearray()

                for chunk in response.iter_content(chunk_size=8192):

                    if not chunk:
                        continue

                    content.extend(chunk)

                    if len(content) > self.max_size:

                        return {
                            "success": False,
                            "redirect": False,
                            "url": url,
                            "status_code": status_code,
                            "error": "HTML page exceeds maximum size",
                            "elapsed_time": time.perf_counter() - start_time
                        }

                encoding = response.encoding or "utf-8"

                html = content.decode(
                    encoding,
                    errors="replace"
                )

                elapsed_time = time.perf_counter() - start_time

                return {
                    "success": True,
                    "redirect": False,
                    "url": url,
                    "html": html,
                    "status_code": status_code,
                    "elapsed_time": elapsed_time,
                    "size_bytes": len(content)
                }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "redirect": False,
                "url": url,
                "status_code": None,
                "error": str(e),
                "elapsed_time": time.perf_counter() - start_time
            }

    def close(self):
        self.session.close()