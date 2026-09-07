# Desktop Widget

A small always-on-top widget showing the current time, Edmonton weather, and
rotating world/business news headlines.

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
- **News sources**: edit the `NEWS_FEEDS` list in `widget.py` — any RSS feed
  URL works.
- **Refresh timing**: `WEATHER_MINUTES`, `NEWS_MINUTES`, and
  `HEADLINE_ROTATE_SECONDS` near the top of `widget.py`.
- **Position**: the widget opens near the top-right of the screen by
  default; drag it anywhere — it does not remember position across
  restarts.
