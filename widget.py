"""Always-on-top desktop widget: time, Edmonton weather, and news headlines."""

import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from json import loads

# Set to True (or run with an env var check) to see per-feed/weather fetch
# errors on stderr when launched as `python widget.py`; silent under
# `pythonw`, which has no console to write to anyway.
DEBUG = False

# Edmonton, AB coordinates.
LATITUDE = 53.5461
LONGITUDE = -113.4938

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LATITUDE}&longitude={LONGITUDE}"
    "&current=temperature_2m,apparent_temperature,weather_code"
    "&timezone=auto"
)

NEWS_FEEDS = [
    # --- World / global -------------------------------------------------
    ("World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("The Economist", "https://www.economist.com/finance-and-economics/rss.xml"),
    ("Hacker News", "https://news.ycombinator.com/rss"),
    # --- Ecuador ----------------------------------------------------------
    ("El Comercio", "https://www.elcomercio.com/feed"),
    ("INEC", "https://www.ecuadorencifras.gob.ec/feed/"),
    # Primicias is a client-rendered SPA with no server-side RSS, and GK
    # and La Hora both return 403 to a plain script request (Cloudflare
    # bot protection) — a site-scoped Google News search is the working
    # substitute for all three.
    (
        "Primicias",
        "https://news.google.com/rss/search?q=site:primicias.ec&hl=es-419&gl=EC&ceid=EC:es-419",
    ),
    (
        "GK",
        "https://news.google.com/rss/search?q=site:gk.city&hl=es-419&gl=EC&ceid=EC:es-419",
    ),
    (
        "La Hora",
        "https://news.google.com/rss/search?q=site:lahora.com.ec&hl=es-419&gl=EC&ceid=EC:es-419",
    ),
    # --- Canada -----------------------------------------------------------
    ("Canada Econ", "https://www.cbc.ca/webfeed/rss/rss-business"),
    ("StatCan", "https://www150.statcan.gc.ca/n1/rss/dai-quo/0-eng.atom"),
    ("Bank of Canada", "https://www.bankofcanada.ca/content_type/press-releases/feed/"),
]

WEATHER_MINUTES = 15
NEWS_MINUTES = 20
HEADLINE_GROUP_SECONDS = 15
# Caps a headline (including its "[Source] " prefix) to roughly 2 wrapped
# lines at HEADLINE_FONT/the headline wraplength. Without this cap, a long
# title (CBC and The Economist both run long) wraps to 3+ lines and the
# fixed-size window — which never resizes to content, unlike a normal
# scrollable feed — clips it instead of showing it in full.
MAX_HEADLINE_CHARS = 85
HEADLINES_PER_FEED = 3
HEADLINES_VISIBLE = 3

# Some feed hosts reject requests with no User-Agent header.
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (desktop-widget)"}

# Caps how much of a response body is read, so a misbehaving or malicious
# host can't exhaust memory by streaming an unbounded body within the
# request timeout; 5 MB comfortably covers any real weather/feed response.
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    # Every source URL in this file is a hardcoded https:// constant;
    # refusing a redirect to a non-https URL stops a compromised or
    # misconfigured host from silently downgrading the connection.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise urllib.error.HTTPError(
                newurl, code, "Refused non-HTTPS redirect", headers, fp
            )

        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_HttpsOnlyRedirectHandler)


def _log_fetch_error(label: str, exc: Exception) -> None:
    if DEBUG:
        print(f"[{label}] fetch error: {exc}", file=sys.stderr)

SMALL_WIDTH, SMALL_HEIGHT = 195, 105
FULL_WIDTH, FULL_HEIGHT = 300, 400

# Matches the Libertinus serif face used in Daniel's ECON 899 paper —
# Libertinus itself isn't registered as a system font on Windows, but
# Garamond (installed) gives the widget the same serif, academic feel.
TEXT_FAMILY = "Garamond"

TIME_FONT_FULL = (TEXT_FAMILY, 28)
TIME_FONT_SMALL = (TEXT_FAMILY, 20)
DATE_FONT = (TEXT_FAMILY, 11)
WEATHER_ICON_FONT_FULL = ("Segoe UI Emoji", 22)
WEATHER_ICON_FONT_SMALL = ("Segoe UI Emoji", 16)
WEATHER_TEXT_FONT_FULL = (TEXT_FAMILY, 12)
WEATHER_TEXT_FONT_SMALL = (TEXT_FAMILY, 10)
HEADLINE_FONT = (TEXT_FAMILY, 13)

# WMO weather codes (Open-Meteo), grouped into short display text and icon.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ hail",
    99: "Thunderstorm w/ hail",
}

WEATHER_ICONS = {
    0: "☀️",
    1: "🌤️",
    2: "⛅",
    3: "☁️",
    45: "🌫️",
    48: "🌫️",
    51: "🌦️",
    53: "🌦️",
    55: "🌦️",
    61: "🌧️",
    63: "🌧️",
    65: "🌧️",
    66: "🌧️",
    67: "🌧️",
    71: "🌨️",
    73: "🌨️",
    75: "🌨️",
    77: "🌨️",
    80: "🌦️",
    81: "🌧️",
    82: "🌧️",
    85: "🌨️",
    86: "🌨️",
    95: "⛈️",
    96: "⛈️",
    99: "⛈️",
}

BACKGROUND = "#1e1e1e"
FOREGROUND = "#e6e6e6"
ACCENT = "#8ab4f8"
MUTED = "#9a9a9a"


def fetch_weather() -> tuple[str, str]:
    request = urllib.request.Request(WEATHER_URL, headers=REQUEST_HEADERS)

    with _OPENER.open(request, timeout=10) as response:
        payload = loads(response.read(MAX_RESPONSE_BYTES))

    current = payload["current"]
    temperature = round(current["temperature_2m"])
    feels_like = round(current["apparent_temperature"])
    code = current["weather_code"]
    condition = WEATHER_CODES.get(code, "Unknown")
    icon = WEATHER_ICONS.get(code, "🌡️")

    text = f"{temperature}°C, {condition}  (feels {feels_like}°C)"
    return icon, text


def _entry_title(entry: ET.Element) -> str:
    title_element = entry.find("{*}title")

    if title_element is None:
        return ""

    # A plain RSS/RDF title is a single text node, so itertext() just
    # yields it. An Atom title with type="xhtml" (e.g. StatCan's feed)
    # nests the real text inside an xhtml <div>/<span>; itertext() walks
    # those children too, so one code path covers both shapes.
    return "".join(title_element.itertext()).strip()


def _entry_link(entry: ET.Element) -> str:
    # RSS/RDF entries have exactly one <link>. Atom entries may have
    # several (rel="self", "alternate", "related", ...) in unspecified
    # order, so pick the one whose rel is "alternate" (Atom's default when
    # rel is omitted) rather than assuming the first <link> is the article.
    link_elements = entry.findall("{*}link")
    chosen = next(
        (el for el in link_elements if el.get("rel", "alternate") == "alternate"),
        link_elements[0] if link_elements else None,
    )

    if chosen is None:
        return ""

    # RSS/RDF put the URL as the element's text; Atom puts it in an
    # href attribute instead.
    link = (chosen.get("href") or chosen.text or "").strip()

    # Only ever hand an http(s) URL to webbrowser.open() downstream — a
    # malicious/compromised feed entry could otherwise supply a file:// or
    # other OS-handler URI.
    if not link.lower().startswith(("http://", "https://")):
        return ""

    return link


def _entry_date(entry: ET.Element) -> str:
    # RSS 2.0 (BBC, El Comercio, CBC, INEC, The Economist, Hacker News,
    # the Google News proxies) uses RFC 822 <pubDate>.
    pub_date = entry.findtext("{*}pubDate")

    if pub_date:
        try:
            return parsedate_to_datetime(pub_date.strip()).strftime("%b %d")
        except (TypeError, ValueError):
            pass

    # Atom (StatCan) uses ISO 8601 <updated>/<published>; RSS 1.0/RDF
    # (Bank of Canada) uses ISO 8601 <dc:date> — "{*}date" ignores the
    # dc: namespace URI and matches on the local tag name alone.
    for tag in ("updated", "published", "date"):
        raw_date = entry.findtext(f"{{*}}{tag}")

        if raw_date:
            # fromisoformat() only accepts a trailing "Z" (Zulu/UTC) suffix
            # from Python 3.11 onward; normalize it to an explicit +00:00
            # offset so this also parses correctly on 3.9/3.10, which the
            # README lists as the minimum supported version.
            normalized_date = raw_date.strip()

            if normalized_date.endswith("Z"):
                normalized_date = normalized_date[:-1] + "+00:00"

            try:
                return datetime.fromisoformat(normalized_date).strftime("%b %d")
            except ValueError:
                continue

    # No recognized date field on this entry.
    return ""


def fetch_one_feed(feed_url: str) -> list[tuple[str, str, str]]:
    request = urllib.request.Request(feed_url, headers=REQUEST_HEADERS)

    with _OPENER.open(request, timeout=10) as response:
        # A leading byte-order mark or stray whitespace before the XML
        # declaration (seen on some feeds, e.g. INEC's) makes ElementTree
        # reject an otherwise valid document.
        raw = response.read(MAX_RESPONSE_BYTES).lstrip()

    root = ET.fromstring(raw)

    # "{*}item"/"{*}entry" match RSS 2.0 (<item>, no namespace), RSS
    # 1.0/RDF (e.g. Bank of Canada's, namespaced), and Atom (<entry>,
    # e.g. StatCan's) alike — "./channel/item" would miss the latter two.
    entries = root.findall(".//{*}item") or root.findall(".//{*}entry")
    entries = entries[:HEADLINES_PER_FEED]

    return [
        (_entry_title(entry), _entry_link(entry), _entry_date(entry))
        for entry in entries
    ]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text

    return text[: limit - 1].rstrip() + "…"


def _format_headline(source: str, title: str, date: str, limit: int) -> str:
    prefix = f"[{source}] "
    # Every headline gets a "(...)" suffix; if a feed has no date field
    # at all, "new" is an honest fallback rather than a fabricated date.
    suffix = f" ({date or 'new'})"
    # The suffix must always show in full, so only the title is
    # truncated to fit what's left of the character budget.
    title_budget = max(limit - len(prefix) - len(suffix), 10)

    return f"{prefix}{_truncate(title, title_budget)}{suffix}"


def fetch_headlines() -> list[tuple[str, str, str, str]]:
    headlines = []

    for label, feed_url in NEWS_FEEDS:
        try:
            feed_items = fetch_one_feed(feed_url)
        except Exception as exc:
            # One unreachable or malformed feed should not blank out the
            # headlines from every other, working feed.
            _log_fetch_error(label, exc)
            continue

        for title, link, date in feed_items:
            headlines.append((label, title, link, date))

    return headlines


class DesktopWidget:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.headlines: list[tuple[str, str, str, str]] = []
        self.visible_headlines: list[tuple[str, str, str, str]] = []
        self.headline_index = 0
        self.expanded = True
        self.minimized = False

        self._configure_window()
        self._build_layout()
        self._apply_initial_geometry()

        self._drag_start_x = 0
        self._drag_start_y = 0

        self._update_clock()
        self._refresh_weather()
        self._refresh_news()
        self._rotate_headline()

    def _configure_window(self) -> None:
        self.root.title("Desktop Widget")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.9)
        self.root.configure(bg=BACKGROUND)

        self.root.bind("<ButtonPress-1>", self._start_drag)
        self.root.bind("<B1-Motion>", self._on_drag)
        self.root.bind("<Map>", self._on_map)

    def _apply_initial_geometry(self) -> None:
        # Pack's propagation recalculates the toplevel's size from its
        # children once they exist, so the fixed size must be applied
        # after the layout is built, not before.
        self.root.update_idletasks()
        # winfo_screenwidth() reports the primary monitor only; on a
        # multi-monitor setup where the primary isn't the rightmost
        # display, "top-right" anchors to the primary monitor's edge, not
        # necessarily the display the user has in mind. Not fixed here —
        # proper multi-monitor placement needs Win32 monitor-enumeration
        # calls, disproportionate for a personal single-file widget.
        screen_width = self.root.winfo_screenwidth()
        x_position = screen_width - FULL_WIDTH - 20
        y_position = 20
        self.root.geometry(f"{FULL_WIDTH}x{FULL_HEIGHT}+{x_position}+{y_position}")

    def _resize_for_mode(self) -> None:
        # Keeps the widget's current top-left corner in place, unlike
        # _apply_initial_geometry, so toggling mode never snaps a
        # user-dragged widget back to its starting corner.
        self.root.update_idletasks()
        width, height = (FULL_WIDTH, FULL_HEIGHT) if self.expanded else (
            SMALL_WIDTH,
            SMALL_HEIGHT,
        )
        x_position = self.root.winfo_x()
        y_position = self.root.winfo_y()
        self.root.geometry(f"{width}x{height}+{x_position}+{y_position}")

    def _make_header_button(
        self, side: str, text: str, command, padx: tuple[int, int] = (0, 0)
    ) -> tk.Label:
        button = tk.Label(self.header, text=text, fg=MUTED, bg=BACKGROUND, cursor="hand2")
        button.pack(side=side, padx=padx)
        button.bind("<Button-1>", lambda _: command())
        return button

    def _build_layout(self) -> None:
        self.header = tk.Frame(self.root, bg=BACKGROUND)
        self.header.pack(fill="x", padx=10, pady=(8, 0))

        self._make_header_button("left", "⟳", self._refresh_all)
        self.mode_button = self._make_header_button(
            "left", "▾", self._toggle_mode, padx=(6, 0)
        )

        # Right-packed widgets stack from the header's right edge inward,
        # so packing close before minimize puts minimize to close's left —
        # the opposite of left-packed insertion order above.
        self._make_header_button("right", "×", self.root.destroy)
        self._make_header_button("right", "–", self._minimize, padx=(0, 6))

        self.time_label = tk.Label(
            self.root, font=TIME_FONT_FULL, fg=FOREGROUND, bg=BACKGROUND
        )
        self.time_label.pack(pady=(4, 0))

        self.date_label = tk.Label(
            self.root, font=DATE_FONT, fg=MUTED, bg=BACKGROUND
        )
        self.date_label.pack()

        self.weather_frame = tk.Frame(self.root, bg=BACKGROUND)
        self.weather_frame.pack(pady=(12, 8))

        self.weather_icon_label = tk.Label(
            self.weather_frame,
            text="…",
            font=WEATHER_ICON_FONT_FULL,
            bg=BACKGROUND,
        )
        self.weather_icon_label.pack(side="left", padx=(0, 8))

        self.weather_text_label = tk.Label(
            self.weather_frame,
            text="Loading weather…",
            font=WEATHER_TEXT_FONT_FULL,
            fg=ACCENT,
            bg=BACKGROUND,
            wraplength=220,
            justify="left",
        )
        self.weather_text_label.pack(side="left")

        self.separator = tk.Frame(self.root, bg="#3a3a3a", height=1)
        self.news_frame = tk.Frame(self.root, bg=BACKGROUND)

        self.headline_labels = []
        for _ in range(HEADLINES_VISIBLE):
            headline_label = tk.Label(
                self.news_frame,
                text="",
                font=HEADLINE_FONT,
                fg=FOREGROUND,
                bg=BACKGROUND,
                wraplength=270,
                justify="left",
                anchor="w",
                cursor="hand2",
            )
            headline_label.pack(fill="x", pady=(0, 6))
            self.headline_labels.append(headline_label)

        for index, headline_label in enumerate(self.headline_labels):
            headline_label.bind(
                "<Button-1>", lambda _event, i=index: self._open_headline(i)
            )

        self._enter_full_mode(resize=False)

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event: tk.Event) -> None:
        new_x = self.root.winfo_x() + event.x - self._drag_start_x
        new_y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{new_x}+{new_y}")

    def _toggle_mode(self) -> None:
        if self.expanded:
            self._enter_small_mode()
        else:
            self._enter_full_mode()

    def _enter_small_mode(self, resize: bool = True) -> None:
        self.separator.pack_forget()
        self.news_frame.pack_forget()
        self.date_label.pack_forget()
        self.expanded = False
        self.mode_button.config(text="▾")

        self.header.pack_configure(pady=(4, 0))
        self.time_label.config(font=TIME_FONT_SMALL)
        self.time_label.pack_configure(pady=(0, 0))
        self.weather_frame.pack_configure(pady=(2, 4))
        self.weather_icon_label.config(font=WEATHER_ICON_FONT_SMALL)
        self.weather_text_label.config(font=WEATHER_TEXT_FONT_SMALL, wraplength=150)

        if resize:
            self._resize_for_mode()

    def _enter_full_mode(self, resize: bool = True) -> None:
        self.header.pack_configure(pady=(8, 0))
        self.time_label.config(font=TIME_FONT_FULL)
        self.time_label.pack_configure(pady=(4, 0))
        self.date_label.pack(before=self.weather_frame)
        self.weather_frame.pack_configure(pady=(12, 8))
        self.weather_icon_label.config(font=WEATHER_ICON_FONT_FULL)
        self.weather_text_label.config(font=WEATHER_TEXT_FONT_FULL, wraplength=220)
        self.separator.pack(fill="x", padx=10, pady=(4, 0))
        self.news_frame.pack(fill="x", padx=10, pady=(10, 0))
        self.expanded = True
        self.mode_button.config(text="▴")

        if resize:
            self._resize_for_mode()

    def _minimize(self) -> None:
        self.minimized = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def _on_map(self, _event: tk.Event) -> None:
        if not self.minimized:
            return

        # Toggling overrideredirect() in _minimize() recreates the
        # underlying OS window, which can fire a transient <Map> event
        # before iconify() actually finishes. Deferring the real check to
        # the next idle cycle avoids misreading that transient event as
        # the user restoring the window mid-minimize.
        self.root.after(50, self._finish_restore_check)

    def _finish_restore_check(self) -> None:
        if not self.minimized:
            return

        if self.root.state() != "normal":
            return

        self.minimized = False
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self._resize_for_mode()

    def _update_clock(self) -> None:
        now = datetime.now()
        self.time_label.config(text=now.strftime("%I:%M:%S %p").lstrip("0"))
        self.date_label.config(text=now.strftime("%A, %B %d"))
        self.root.after(1000, self._update_clock)

    def _refresh_all(self) -> None:
        self._refresh_weather()
        self._refresh_news()

    def _refresh_weather(self) -> None:
        threading.Thread(target=self._fetch_weather_thread, daemon=True).start()
        self.root.after(WEATHER_MINUTES * 60_000, self._refresh_weather)

    def _fetch_weather_thread(self) -> None:
        try:
            icon, text = fetch_weather()
        except Exception as exc:
            _log_fetch_error("weather", exc)
            self._safe_after(0, self._show_weather_error)
            return

        self._safe_after(0, lambda: self._show_weather(icon, text))

    def _safe_after(self, delay_ms: int, callback) -> None:
        # A fetch thread can finish after the user has already closed the
        # widget (root.destroy() on the × button); scheduling against a
        # destroyed root raises TclError, which is otherwise uncaught and
        # invisible under pythonw (no console to show it on).
        try:
            self.root.after(delay_ms, callback)
        except tk.TclError:
            pass

    def _show_weather(self, icon: str, text: str) -> None:
        self.weather_icon_label.config(text=icon)
        self.weather_text_label.config(text=text)

    def _show_weather_error(self) -> None:
        # Keep the last known-good reading on screen through a transient
        # failure (matching how stale headlines are kept below); only show
        # the error text if nothing has loaded yet this session.
        if self.weather_text_label.cget("text") == "Loading weather…":
            self.weather_icon_label.config(text="⚠️")
            self.weather_text_label.config(text="Weather unavailable")

    def _refresh_news(self) -> None:
        threading.Thread(target=self._fetch_news_thread, daemon=True).start()
        self.root.after(NEWS_MINUTES * 60_000, self._refresh_news)

    def _fetch_news_thread(self) -> None:
        try:
            headlines = fetch_headlines()
        except Exception as exc:
            _log_fetch_error("news", exc)
            headlines = []

        self._safe_after(0, lambda: self._store_headlines(headlines))

    def _store_headlines(self, headlines: list[tuple[str, str, str, str]]) -> None:
        if headlines:
            self.headlines = headlines
            self.headline_index = 0
        elif not self.headlines:
            self.headline_labels[0].config(text="News unavailable")
            for headline_label in self.headline_labels[1:]:
                headline_label.config(text="")

    def _rotate_headline(self) -> None:
        if self.headlines:
            total = len(self.headlines)
            visible = [
                self.headlines[(self.headline_index + offset) % total]
                for offset in range(min(HEADLINES_VISIBLE, total))
            ]
            self.visible_headlines = visible

            for index, headline_label in enumerate(self.headline_labels):
                if index < len(visible):
                    source, title, _link, date = visible[index]
                    headline_label.config(
                        text=_format_headline(source, title, date, MAX_HEADLINE_CHARS)
                    )
                else:
                    headline_label.config(text="")

            # Advance by however many headlines were actually shown, not
            # the fixed HEADLINES_VISIBLE constant: when total < that
            # constant (few feeds loaded, or a feed failure), advancing by
            # the fixed amount could skip past entries the shorter list
            # never displayed.
            self.headline_index = (self.headline_index + len(visible)) % total

        self.root.after(HEADLINE_GROUP_SECONDS * 1000, self._rotate_headline)

    def _open_headline(self, index: int) -> None:
        if index >= len(self.visible_headlines):
            return

        _source, _title, link, _date = self.visible_headlines[index]

        if link:
            webbrowser.open(link)


def main() -> None:
    root = tk.Tk()
    DesktopWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
