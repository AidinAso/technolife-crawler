from crawler import Crawler

crawler = Crawler(
    start_url="https://technolife.com/",
    allowed_domain="technolife.com",
    max_pages=5,
    delay=1
)

crawler.crawl()
