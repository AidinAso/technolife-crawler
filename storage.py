import json
from pathlib import Path


class Storage:

    def __init__(self, output_dir="output"):

        self.output_dir = Path(output_dir)
        self.pages_dir = self.output_dir / "pages"

        self.pages_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.metadata_file = self.output_dir / "metadata.jsonl"

        self.saved_pages = 0
        self.total_bytes = 0

        self.metadata_file.write_text("", encoding="utf-8")

    def save(self, url, html):

        page_id = self.saved_pages + 1

        filename = f"page_{page_id:05d}.html"

        filepath = self.pages_dir / filename

        html_bytes = html.encode("utf-8")

        filepath.write_bytes(html_bytes)

        metadata = {
            "id": page_id,
            "url": url,
            "file": f"pages/{filename}",
            "size_bytes": len(html_bytes)
        }

        with self.metadata_file.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                json.dumps(metadata, ensure_ascii=False) + "\n"
            )

        self.saved_pages += 1
        self.total_bytes += len(html_bytes)

        return metadata

    def get_total_size(self):

        return self.total_bytes