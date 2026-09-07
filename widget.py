"""Always-on-top desktop widget: time, Edmonton weather, and news headlines."""

import threading
import tkinter as tk
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from json import loads

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
    ("World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Ecuador", "https://www.elcomercio.com/feed"),
    ("Econ Research", "https://www.nber.org/rss/new.xml"),
    ("Canada Econ", "https://www.cbc.ca/webfeed/rss/rss-business"),
    ("Hacker News", "https://news.ycombinator.com/rss"),
    ("INEC", "https://www.ecuadorencifras.gob.ec/feed/"),
    ("StatCan", "https://www150.statcan.gc.ca/n1/rss/dai-quo/0-eng.atom"),
    # VoxEU's own rss.xml only lists research-programme categories, not
    # columns, since the site merged into cepr.org — same substitution.
    (
        "VoxEU",
        "https://news.google.com/rss/search?q=site:cepr.org/voxeu&hl=en-GB&gl=GB&ceid=GB:en",
    ),
    ("Bank of Canada", "https://www.bankofcanada.ca/content_type/press-releases/feed/"),
]

WEATHER_MINUTES = 15
NEWS_MINUTES = 20
HEADLINE_GROUP_SECONDS = 15
HEADLINES_PER_FEED = 3
HEADLINES_VISIBLE = 3

# Some feed hosts reject requests with no User-Agent header.
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (desktop-widget)"}

SMALL_WIDTH, SMALL_HEIGHT = 280, 150
FULL_WIDTH, FULL_HEIGHT = 300, 380

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

    with urllib.request.urlopen(request, timeout=10) as response:
        payload = loads(response.read())

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
    link_element = entry.find("{*}link")

    if link_element is None:
        return ""

    # RSS/RDF put the URL as the element's text; Atom puts it in an
    # href attribute instead.
    return (link_element.get("href") or link_element.text or "").strip()


def fetch_one_feed(feed_url: str) -> list[tuple[str, str]]:
    request = urllib.request.Request(feed_url, headers=REQUEST_HEADERS)

    with urllib.request.urlopen(request, timeout=10) as response:
        # A leading byte-order mark or stray whitespace before the XML
        # declaration (seen on some feeds, e.g. INEC's) makes ElementTree
        # reject an otherwise valid document.
        raw = response.read().lstrip()

    root = ET.fromstring(raw)

    # "{*}item"/"{*}entry" match RSS 2.0 (<item>, no namespace), RSS
    # 1.0/RDF (e.g. Bank of Canada's, namespaced), and Atom (<entry>,
    # e.g. StatCan's) alike — "./channel/item" would miss the latter two.
    entries = root.findall(".//{*}item") or root.findall(".//{*}entry")
    entries = entries[:HEADLINES_PER_FEED]

    return [(_entry_title(entry), _entry_link(entry)) for entry in entries]


def fetch_headlines() -> list[tuple[str, str, str]]:
    headlines = []

    for label, feed_url in NEWS_FEEDS:
        try:
            feed_items = fetch_one_feed(feed_url)
        except Exception:
            # One unreachable or malformed feed should not blank out the
            # headlines from every other, working feed.
            continue

        for title, link in feed_items:
            headlines.append((label, title, link))

    return headlines


class DesktopWidget:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.headlines: list[tuple[str, str, str]] = []
        self.visible_headlines: list[tuple[str, str, str]] = []
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

    def _build_layout(self) -> None:
        header = tk.Frame(self.root, bg=BACKGROUND)
        header.pack(fill="x", padx=10, pady=(8, 0))

        refresh_button = tk.Label(
            header, text="⟳", fg=MUTED, bg=BACKGROUND, cursor="hand2"
        )
        refresh_button.pack(side="left")
        refresh_button.bind("<Button-1>", lambda _: self._refresh_all())

        self.mode_button = tk.Label(
            header, text="▾", fg=MUTED, bg=BACKGROUND, cursor="hand2"
        )
        self.mode_button.pack(side="left", padx=(6, 0))
        self.mode_button.bind("<Button-1>", lambda _: self._toggle_mode())

        close_button = tk.Label(
            header, text="×", fg=MUTED, bg=BACKGROUND, cursor="hand2"
        )
        close_button.pack(side="right")
        close_button.bind("<Button-1>", lambda _: self.root.destroy())

        minimize_button = tk.Label(
            header, text="–", fg=MUTED, bg=BACKGROUND, cursor="hand2"
        )
        minimize_button.pack(side="right", padx=(0, 6))
        minimize_button.bind("<Button-1>", lambda _: self._minimize())

        self.time_label = tk.Label(
            self.root, font=("Segoe UI", 26), fg=FOREGROUND, bg=BACKGROUND
        )
        self.time_label.pack(pady=(4, 0))

        self.date_label = tk.Label(
            self.root, font=("Segoe UI", 10), fg=MUTED, bg=BACKGROUND
        )
        self.date_label.pack()

        weather_frame = tk.Frame(self.root, bg=BACKGROUND)
        weather_frame.pack(pady=(12, 8))

        self.weather_icon_label = tk.Label(
            weather_frame,
            text="…",
            font=("Segoe UI Emoji", 22),
            bg=BACKGROUND,
        )
        self.weather_icon_label.pack(side="left", padx=(0, 8))

        self.weather_text_label = tk.Label(
            weather_frame,
            text="Loading weather…",
            font=("Segoe UI", 11),
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
                font=("Segoe UI", 9),
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
        self.expanded = False
        self.mode_button.config(text="▾")

        if resize:
            self._resize_for_mode()

    def _enter_full_mode(self, resize: bool = True) -> None:
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
        except Exception:
            icon, text = "⚠️", "Weather unavailable"

        self.root.after(0, lambda: self._show_weather(icon, text))

    def _show_weather(self, icon: str, text: str) -> None:
        self.weather_icon_label.config(text=icon)
        self.weather_text_label.config(text=text)

    def _refresh_news(self) -> None:
        threading.Thread(target=self._fetch_news_thread, daemon=True).start()
        self.root.after(NEWS_MINUTES * 60_000, self._refresh_news)

    def _fetch_news_thread(self) -> None:
        try:
            headlines = fetch_headlines()
        except Exception:
            headlines = []

        self.root.after(0, lambda: self._store_headlines(headlines))

    def _store_headlines(self, headlines: list[tuple[str, str, str]]) -> None:
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
                    source, title, _link = visible[index]
                    headline_label.config(text=f"[{source}] {title}")
                else:
                    headline_label.config(text="")

            self.headline_index = (self.headline_index + HEADLINES_VISIBLE) % total

        self.root.after(HEADLINE_GROUP_SECONDS * 1000, self._rotate_headline)

    def _open_headline(self, index: int) -> None:
        if index >= len(self.visible_headlines):
            return

        _source, _title, link = self.visible_headlines[index]

        if link:
            webbrowser.open(link)


def main() -> None:
    root = tk.Tk()
    DesktopWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
