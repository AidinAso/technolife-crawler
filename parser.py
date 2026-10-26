from bs4 import BeautifulSoup
from urllib.parse import urljoin


class Parser:

    def extract_links(self, html, base_url):

        soup = BeautifulSoup(html, "html.parser")

        links = []

        for tag in soup.find_all("a", href=True):

            href = tag["href"].strip()

            if not href:
                continue

            full_url = urljoin(base_url, href)

            links.append(full_url)

        return links