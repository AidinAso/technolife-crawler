import time
from urllib.parse import urljoin

from queue_manager import URLQueue
from url_checker import URLChecker
from fetcher import Fetcher
from parser import Parser
from storage import Storage
from robots_checker import RobotsChecker


class Crawler:

    def __init__(
        self,
        start_url,
        allowed_domain,
        max_pages=10,
        delay=2
    ):

        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay

        self.queue = URLQueue()
        self.checker = URLChecker(allowed_domain)
        self.fetcher = Fetcher()
        self.parser = Parser()
        self.storage = Storage()
        self.robots_checker = RobotsChecker()

        self.downloaded_pages = 0
        self.discovered_urls = 0
        self.errors = 0
        self.redirects = 0
        self.skipped_robots = 0

        self.last_request_time = None

    def wait_before_request(self):

        if self.last_request_time is not None:

            elapsed = time.monotonic() - self.last_request_time

            remaining = self.delay - elapsed

            if remaining > 0:
                time.sleep(remaining)

    def crawl(self):

        start_time = time.perf_counter()

        try:

            first_url = self.checker.check(self.start_url)

            if first_url is None:
                print("Start URL is not valid.")
                return

            if not self.robots_checker.is_allowed(first_url):
                print("Start URL is disallowed by robots.txt.")
                return

            self.queue.enqueue(first_url)

            while (
                not self.queue.is_empty()
                and self.downloaded_pages < self.max_pages
            ):

                current_url = self.queue.dequeue()

                if not self.robots_checker.is_allowed(current_url):

                    self.skipped_robots += 1

                    print("Skipped by robots.txt:", current_url)

                    continue

                self.wait_before_request()

                print(f"\nFetching: {current_url}")

                self.last_request_time = time.monotonic()

                result = self.fetcher.fetch(current_url)

                print(
                    "Request time:",
                    round(result.get("elapsed_time", 0), 3),
                    "seconds"
                )

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

                                print(
                                    "Redirect queued:",
                                    checked_url
                                )

                            else:

                                self.skipped_robots += 1

                                print(
                                    "Redirect blocked by robots.txt:",
                                    checked_url
                                )

                    continue

                if not result["success"]:

                    self.errors += 1

                    print("Error:", result.get("error", "Unknown fetch error"))

                    if result.get("status_code") in (429, 503):

                        print(
                            "Server requested reduced traffic. "
                            "Stopping crawler."
                        )

                        break

                    continue

                metadata = self.storage.save(
                    result["url"],
                    result["html"]
                )

                self.downloaded_pages += 1

                print(
                    "Downloaded pages:",
                    self.downloaded_pages
                )

                print(
                    "Saved file:",
                    metadata["file"]
                )

                links = self.parser.extract_links(
                    result["html"],
                    result["url"]
                )

                self.discovered_urls += len(links)

                for link in links:

                    checked_url = self.checker.check(link)

                    if checked_url is not None:

                        self.queue.enqueue(checked_url)

                print(
                    "Queue size:",
                    self.queue.size()
                )

        finally:

            self.fetcher.close()
            self.robots_checker.close()

            elapsed_time = time.perf_counter() - start_time

            print("\n========== CRAWL REPORT ==========")

            print("Downloaded pages:", self.downloaded_pages)

            print(
                "Discovered URLs (with duplicates):",
                self.discovered_urls
            )

            print(
                "Remaining queue size:",
                self.queue.size()
            )

            print("Errors:", self.errors)

            print("Redirects:", self.redirects)

            print(
                "Skipped by robots.txt:",
                self.skipped_robots
            )

            print(
                "Crawl time:",
                round(elapsed_time, 2),
                "seconds"
            )

            print(
                "Saved HTML files:",
                self.storage.saved_pages
            )

            print(
                "Total HTML size:",
                round(
                    self.storage.get_total_size() / 1024,
                    2
                ),
                "KB"
            )