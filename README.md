# Desktop Widget

A small, borderless, always-on-top Windows widget showing the current time,
Edmonton weather (with a condition icon), and rotating headlines from 14
news and research sources.

## Features

- **Live clock and date**, updating every second.
- **Weather**: current temperature, "feels like," and a condition icon
  (☀️ ⛅ ☁️ 🌧️ 🌨️ ⛈️ etc.) for Edmonton, AB, via [Open-Meteo](https://open-meteo.com/)
  (no API key required).
- **News**: 3 headlines shown at once, in a small serif font, rotating to
  the next 3 every 15 seconds. Click any headline to open it in your
  browser.
- **Three view states**:
  - **Full** — time, weather, and news.
  - **Small** — time and weather only, in a noticeably tighter window.
    Toggle between the two with the **▾ / ▴** button.
  - **Minimized** — sent to the Windows taskbar with the **–** button;
    click its taskbar icon to bring it back exactly where it was.
- **Garamond** throughout, for a more editorial/academic look than the
  default UI font.
- Draggable (click and drag anywhere on the background) and
  semi-transparent, so it never fully blocks what's behind it.

## News sources

| Label | Source | Notes |
|---|---|---|
| World | BBC World | official RSS |
| Business | BBC Business | official RSS |
| El Comercio | El Comercio (Ecuador) | official RSS |
| Primicias | Primicias (Ecuador) | via Google News*, site has no server-side RSS |
| GK | gk.city (Ecuador) | via Google News*, site blocks direct RSS requests |
| La Hora | Diario La Hora (Ecuador) | via Google News*, site blocks direct RSS requests |
| INEC | Ecuador's national statistics institute | official RSS |
| Econ Research | NBER new working papers | official RSS |
| Canada Econ | CBC Business | official RSS |
| StatCan | Statistics Canada, "The Daily" | official Atom feed |
| Bank of Canada | Bank of Canada press releases | official RSS (RSS 1.0/RDF) |
| VoxEU | VoxEU / CEPR columns | via Google News*, voxeu.org's own feed only lists topic categories |
| The Economist | Finance & Economics section | official RSS (economist.com/rss itself returns 403) |
| Hacker News | Hacker News front page | official RSS |

\* A handful of sites don't expose a working RSS/Atom feed for scripted
requests (client-rendered pages, or bot-protection that 403s a plain
request). For those, the widget substitutes a Google News search scoped to
that site (`site:example.com`) as the closest working equivalent — real
headlines from that outlet, just Google-mediated rather than the
publisher's own feed.

The parser (`fetch_one_feed` in `widget.py`) handles all three shapes these
sources come in: RSS 2.0, RSS 1.0/RDF (Bank of Canada), and Atom (StatCan) —
including Atom's XHTML-typed titles and `href`-attribute links. Each feed is
fetched independently, so one broken or slow source never blanks out
headlines from the others.

## Requirements

- Python 3.9+ on Windows (tkinter ships with the standard Windows installer;
  no extra `pip install` needed).
- An internet connection for weather and news.

## Run it

Double-click `run_widget.vbs`, or from a terminal:

```bash
pythonw widget.py
```

(`pythonw` avoids a console window; plain `python widget.py` also works and
is useful for seeing error output while testing.)

## Turn it off

- Click the **×** in the widget's top-right corner.
- If it ever hangs: open Task Manager (Ctrl+Shift+Esc), find `pythonw.exe`
  (or `python.exe`), and End Task.

## Turn it back on

The widget is borderless, so it has no taskbar icon to click while it's
running — and none to bring back once you've closed it. Use the
**"Desktop Widget"** shortcut on your Desktop (double-click it) instead of
re-running the script by hand.

## Runs automatically at login

A copy of that same shortcut lives in your Startup folder
(`shell:startup`), so the widget launches on its own every time you log in
to Windows. To stop that:

1. Press `Win+R`, type `shell:startup`, press Enter.
2. Delete `Desktop Widget.lnk` from that folder.

Deleting it only stops the auto-launch — the Desktop shortcut still works
to start the widget manually.

## Customizing

- **Location**: edit `LATITUDE`/`LONGITUDE` in `widget.py` (currently
  Edmonton, AB).
- **News sources**: edit the `NEWS_FEEDS` list in `widget.py` — any RSS or
  Atom feed URL works, official or a Google News site-search substitute.
- **Font**: `TEXT_FAMILY` near the top of `widget.py` (currently
  `"Garamond"`).
- **Refresh timing**: `WEATHER_MINUTES`, `NEWS_MINUTES`, and
  `HEADLINE_GROUP_SECONDS` (how often the visible group of 3 headlines
  rotates) near the top of `widget.py`.
- **Headlines per source / visible at once**: `HEADLINES_PER_FEED` and
  `HEADLINES_VISIBLE`.
- **Position**: the widget opens near the top-right of the screen by
  default; drag it anywhere — it does not remember position across
  restarts.
