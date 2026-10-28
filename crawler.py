import time
from urllib.parse import urljoin

from queue_manager import URLQueue
from url_checker import URLChecker
from fetcher import Fetcher
from parser import Parser
from storage import Storage
from robots_checker import RobotsChecker
from ui import CrawlerUI


class Crawler:

    def __init__(
        self,
        start_url,
        allowed_domain,
        max_pages=10,
        delay=2
    ):

        self.start_url = start_url
        self.allowed_domain = allowed_domain
        self.max_pages = max_pages
        self.delay = delay

        self.ui = CrawlerUI(max_pages)

        self.queue = URLQueue()
        self.checker = URLChecker(allowed_domain)
        self.fetcher = Fetcher()
        self.parser = Parser()
        self.storage = Storage()
        self.robots_checker = RobotsChecker(on_warning=self.ui.warn)

        self.downloaded_pages = 0
        self.discovered_urls = 0
        self.errors = 0
        self.redirects = 0
        self.skipped_robots = 0

        self.request_count = 0
        self.total_request_time = 0.0

        self.last_request_time = None
        self.crawl_started_at = None

        self.stop_status = None
        self.stop_reason = None

    def wait_before_request(self):

        if self.last_request_time is not None:

            elapsed = time.monotonic() - self.last_request_time

            remaining = self.delay - elapsed

            if remaining > 0:
                self.ui.waiting(remaining)
                time.sleep(remaining)

    def stop(self, status, reason):

        self.stop_status = status
        self.stop_reason = reason

    def get_stats(self):

        elapsed = time.perf_counter() - self.crawl_started_at

        avg_response = None

        if self.request_count:
            avg_response = self.total_request_time / self.request_count

        pages_per_min = None

        if self.downloaded_pages and elapsed > 0:
            pages_per_min = self.downloaded_pages / elapsed * 60

        return {
            "downloaded": self.downloaded_pages,
            "queue": self.queue.size(),
            "discovered": self.discovered_urls,
            "errors": self.errors,
            "redirects": self.redirects,
            "robots": self.skipped_robots,
            "total_bytes": self.storage.get_total_size(),
            "avg_response": avg_response,
            "pages_per_min": pages_per_min
        }

    def refresh_ui(self):

        self.ui.update_stats(**self.get_stats())

    def crawl(self):

        self.crawl_started_at = time.perf_counter()

        self.ui.header(
            self.start_url,
            self.allowed_domain,
            self.max_pages,
            self.delay,
            self.storage.output_dir.resolve()
        )

        self.ui.start()

        try:

            self.ui.set_status("Checking", "start URL and robots.txt")

            first_url = self.checker.check(self.start_url)

            if first_url is None:
                self.stop("error", "Start URL is not valid")
                return

            if not self.robots_checker.is_allowed(first_url):
                self.stop("error", "Start URL is disallowed by robots.txt")
                return

            self.queue.enqueue(first_url)

            while (
                not self.queue.is_empty()
                and self.downloaded_pages < self.max_pages
            ):

                current_url = self.queue.dequeue()

                if not self.robots_checker.is_allowed(current_url):

                    self.skipped_robots += 1

                    self.ui.blocked(current_url)
                    self.refresh_ui()

                    continue

                self.wait_before_request()

                self.ui.fetching(current_url)

                self.last_request_time = time.monotonic()

                result = self.fetcher.fetch(current_url)

                self.request_count += 1
                self.total_request_time += result.get("elapsed_time", 0)

                if result.get("redirect"):

                    self.redirects += 1

                    location = result.get("location")

                    if location:

                        redirect_url = urljoin(
                            current_url,
                            location
                        )

                        checked_url = self.checker.check(
                            redirect_url
                        )

                        if checked_url is not None:

                            if self.robots_checker.is_allowed(
                                checked_url
                            ):

                                self.queue.enqueue(checked_url)

                                outcome = "queued"

                            else:

                                self.skipped_robots += 1

                                outcome = "blocked by robots.txt"

                        else:

                            outcome = "ignored (seen / external)"

                        self.ui.redirect(
                            current_url,
                            redirect_url,
                            result.get("status_code"),
                            outcome
                        )

                    self.refresh_ui()

                    continue

                if not result["success"]:

                    self.errors += 1

                    self.ui.failed(
                        current_url,
                        result.get("error", "Unknown fetch error"),
                        result.get("status_code")
                    )

                    self.refresh_ui()

                    if result.get("status_code") in (429, 503):

                        self.stop(
                            "warn",
                            f"Server requested reduced traffic "
                            f"(HTTP {result.get('status_code')}) - crawler stopped"
                        )

                        break

                    continue

                metadata = self.storage.save(
                    result["url"],
                    result["html"]
                )

                self.downloaded_pages += 1

                self.ui.saved(
                    metadata["id"],
                    result["url"],
                    metadata["size_bytes"],
                    result.get("elapsed_time", 0),
                    result.get("status_code")
                )

                self.ui.advance()

                links = self.parser.extract_links(
                    result["html"],
                    result["url"]
                )

                self.discovered_urls += len(links)

                for link in links:

                    checked_url = self.checker.check(link)

                    if checked_url is not None:

                        self.queue.enqueue(checked_url)

                self.refresh_ui()

            if self.stop_reason is None:

                if self.downloaded_pages >= self.max_pages:

                    self.stop(
                        "ok",
                        f"Reached the page limit ({self.max_pages} pages)"
                    )

                else:

                    self.stop(
                        "ok",
                        "Queue is empty - nothing left to crawl"
                    )

        except KeyboardInterrupt:

            self.stop("warn", "Interrupted by user (Ctrl+C)")

        finally:

            self.fetcher.close()
            self.robots_checker.close()

            if self.stop_reason is None:
                self.stop("error", "Stopped by an unexpected error")

            self.ui.stop()

            self.ui.report(
                self.get_stats(),
                self.stop_status,
                self.stop_reason,
                time.perf_counter() - self.crawl_started_at,
                self.storage.output_dir.resolve()
            )
