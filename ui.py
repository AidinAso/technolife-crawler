import threading
from collections import deque
from datetime import datetime
from urllib.parse import urlsplit

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text


def human_size(num_bytes):

    size = float(num_bytes)

    for unit in ("B", "KB", "MB", "GB"):

        if size < 1024 or unit == "GB":

            if unit == "B":
                return f"{int(size)} {unit}"

            return f"{size:.2f} {unit}"

        size /= 1024


def human_duration(seconds):

    seconds = int(round(seconds))

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"

    if minutes:
        return f"{minutes}m {secs:02d}s"

    return f"{secs}s"


def short_url(url):
    """Show only path + query (the domain is the same for every page)."""

    parts = urlsplit(url)

    text = parts.path or "/"

    if parts.query:
        text += "?" + parts.query

    if parts.netloc and not text.startswith("/"):
        text = parts.netloc + text

    return text


class CrawlerUI:
    """Live terminal dashboard for the crawler (built on top of `rich`)."""

    LOG_STYLES = {
        "saved": ("✔", "SAVED", "green"),
        "redirect": ("↪", "REDIRECT", "yellow"),
        "error": ("✖", "ERROR", "bold red"),
        "robots": ("⊘", "ROBOTS", "magenta"),
        "warn": ("!", "WARN", "yellow"),
    }

    def __init__(self, max_pages, log_size=8):

        self.console = Console()
        self.max_pages = max_pages
        self.log_size = log_size

        self._lock = threading.Lock()
        self._log = deque(maxlen=log_size)
        self._status = ("Starting", "")

        self._stats = {
            "downloaded": 0,
            "queue": 0,
            "discovered": 0,
            "errors": 0,
            "redirects": 0,
            "robots": 0,
            "total_bytes": 0,
            "avg_response": None,
            "pages_per_min": None,
        }

        self._progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold]Crawling[/bold]"),
            BarColumn(
                bar_width=None,
                complete_style="green",
                finished_style="green",
                pulse_style="cyan",
            ),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TextColumn("[dim]elapsed[/dim]"),
            TimeElapsedColumn(),
            TextColumn("[dim]eta[/dim]"),
            TimeRemainingColumn(),
            expand=True,
        )

        self._task = self._progress.add_task("crawl", total=max_pages)

        self._live = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def header(self, start_url, domain, max_pages, delay, output_dir):

        info = Table.grid(padding=(0, 2))
        info.add_column(justify="right", style="dim")
        info.add_column()

        info.add_row("Start URL", Text(start_url, style="bold"))
        info.add_row("Domain", domain)
        info.add_row("Max pages", str(max_pages))
        info.add_row("Delay", f"{delay}s between requests")
        info.add_row("Output", str(output_dir))
        info.add_row("Started", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self.console.print()
        self.console.print(
            Panel(
                info,
                title=f"[bold cyan]Web Crawler[/bold cyan] [dim]·[/dim] {domain}",
                title_align="left",
                subtitle="[dim]polite · robots.txt aware[/dim]",
                subtitle_align="right",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    def start(self):

        self._live = Live(
            get_renderable=self._render,
            console=self.console,
            refresh_per_second=12,
            transient=True,
        )

        self._live.start()

    def stop(self):

        if self._live is not None:
            self._live.stop()
            self._live = None

    # ------------------------------------------------------------------
    # State updates (called by the crawler)
    # ------------------------------------------------------------------

    def set_status(self, verb, detail=""):

        with self._lock:
            self._status = (verb, detail)

    def fetching(self, url):

        self.set_status("Fetching", short_url(url))

    def waiting(self, seconds):

        self.set_status("Waiting", f"{seconds:.1f}s (politeness delay)")

    def advance(self):

        self._progress.advance(self._task)

    def update_stats(self, **values):

        with self._lock:
            self._stats.update(values)

    # ------------------------------------------------------------------
    # Log events
    # ------------------------------------------------------------------

    def _add_log(self, kind, target, meta=""):

        with self._lock:
            self._log.append(
                (datetime.now().strftime("%H:%M:%S"), kind, target, meta)
            )

    def saved(self, page_id, url, size_bytes, elapsed, status_code):

        self._add_log(
            "saved",
            f"#{page_id:03d}  {short_url(url)}",
            f"{human_size(size_bytes):>9}  {elapsed:.2f}s  {status_code}",
        )

    def redirect(self, url, location, status_code, outcome):

        self._add_log(
            "redirect",
            f"{short_url(url)} → {short_url(location)}",
            f"{status_code}  {outcome}",
        )

    def failed(self, url, error, status_code=None):

        meta = str(error)

        if len(meta) > 40:
            meta = meta[:37] + "..."

        self._add_log("error", short_url(url), meta)

    def blocked(self, url):

        self._add_log("robots", short_url(url), "disallowed by robots.txt")

    def warn(self, message):

        self._add_log("warn", str(message))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _status_line(self):

        with self._lock:
            verb, detail = self._status

        line = Text(no_wrap=True, overflow="ellipsis")
        line.append("  ➜ ", style="cyan")
        line.append(f"{verb:<9}", style="bold")
        line.append(detail, style="dim")

        return line

    def _stat_cell(self, label, value, style="white"):

        cell = Text(no_wrap=True)
        cell.append(f"{label}\n", style="dim")
        cell.append(value, style=f"bold {style}")

        return cell

    def _stats_panel(self):

        with self._lock:
            s = dict(self._stats)

        avg = s["avg_response"]
        speed = s["pages_per_min"]

        grid = Table.grid(expand=True, padding=(0, 2))

        for _ in range(3):
            grid.add_column(ratio=1)

        grid.add_row(
            self._stat_cell("Pages saved", f"{s['downloaded']}", "green"),
            self._stat_cell("Queue", f"{s['queue']:,}", "cyan"),
            self._stat_cell("Links found", f"{s['discovered']:,}", "blue"),
        )

        grid.add_row("", "", "")

        grid.add_row(
            self._stat_cell(
                "Errors", f"{s['errors']}", "red" if s["errors"] else "white"
            ),
            self._stat_cell(
                "Redirects",
                f"{s['redirects']}",
                "yellow" if s["redirects"] else "white",
            ),
            self._stat_cell(
                "Blocked (robots)",
                f"{s['robots']}",
                "magenta" if s["robots"] else "white",
            ),
        )

        grid.add_row("", "", "")

        grid.add_row(
            self._stat_cell("Data size", human_size(s["total_bytes"])),
            self._stat_cell(
                "Avg response", f"{avg:.2f}s" if avg is not None else "–"
            ),
            self._stat_cell(
                "Speed", f"{speed:.1f} pages/min" if speed else "–"
            ),
        )

        return Panel(
            grid,
            title="Stats",
            title_align="left",
            border_style="blue",
            box=box.ROUNDED,
            padding=(0, 2),
        )

    def _log_panel(self):

        with self._lock:
            entries = list(self._log)

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(no_wrap=True)
        grid.add_column(no_wrap=True)
        grid.add_column(no_wrap=True, min_width=8)
        grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        grid.add_column(no_wrap=True, justify="right")

        if not entries:
            grid.add_row("", "", "", Text("Waiting for first response…", style="dim"), "")

        for clock, kind, target, meta in entries:

            icon, label, style = self.LOG_STYLES[kind]

            grid.add_row(
                Text(clock, style="dim"),
                Text(icon, style=style),
                Text(label, style=style),
                Text(target, no_wrap=True, overflow="ellipsis"),
                Text(meta, style="dim"),
            )

        # keep a constant height so the dashboard does not jump around
        for _ in range(self.log_size - max(len(entries), 1)):
            grid.add_row("", "", "", "", "")

        return Panel(
            grid,
            title="Recent activity",
            title_align="left",
            border_style="grey50",
            box=box.ROUNDED,
            padding=(0, 2),
        )

    def _render(self):

        return Group(
            self._progress,
            self._status_line(),
            self._stats_panel(),
            self._log_panel(),
        )

    # ------------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------------

    def report(self, stats, status, reason, elapsed, output_dir):

        colors = {"ok": "green", "warn": "yellow", "error": "red"}
        icons = {"ok": "✔", "warn": "!", "error": "✖"}

        color = colors.get(status, "white")

        table = Table.grid(padding=(0, 3))
        table.add_column(style="dim", justify="right")
        table.add_column()

        avg = stats.get("avg_response")
        speed = stats.get("pages_per_min")

        table.add_row("Pages saved", f"[bold green]{stats['downloaded']}[/bold green]")
        table.add_row("Total HTML size", human_size(stats["total_bytes"]))
        table.add_row("Links discovered", f"{stats['discovered']:,} [dim](with duplicates)[/dim]")
        table.add_row("Remaining in queue", f"{stats['queue']:,}")
        table.add_row("Redirects", str(stats["redirects"]))
        table.add_row(
            "Errors",
            f"[bold red]{stats['errors']}[/bold red]" if stats["errors"] else "0",
        )
        table.add_row("Blocked by robots.txt", str(stats["robots"]))
        table.add_row("Avg response time", f"{avg:.2f}s" if avg is not None else "–")
        table.add_row("Crawl time", human_duration(elapsed))
        table.add_row("Speed", f"{speed:.1f} pages/min" if speed else "–")
        table.add_row("Saved to", str(output_dir))

        self.console.print(
            Panel(
                table,
                title=f"[bold {color}]{icons.get(status, '')} Crawl report[/bold {color}]",
                title_align="left",
                subtitle=f"[{color}]{reason}[/{color}]",
                subtitle_align="left",
                border_style=color,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        self.console.print()
