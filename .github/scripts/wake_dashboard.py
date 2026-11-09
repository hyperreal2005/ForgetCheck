"""Open the hosted dashboard in a headless browser, waking it if it has gone to sleep.

Streamlit Community Cloud puts an app to sleep after 12 hours without a viewer, and only a real
browser session counts as one: a plain HTTP request reaches Streamlit's own front page, not the
app. Run on a schedule by .github/workflows/keep-awake.yml; exits non-zero if the dashboard does
not load, so a failed run is a "the dashboard is down" email.

    python .github/scripts/wake_dashboard.py https://<app>.streamlit.app
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

# The sleeping page's button ("Yes, get this app back up!").
WAKE = re.compile(r"get this app back up", re.I)
# The landing page's title: present only once the app has started and run its script.
READY = "T.R.A.C.E."
# A cold start installs the requirements and boots the app: a few minutes at worst.
DEADLINE_S = 420
# Stay on the page after it loads, so the visit registers as a viewer session.
LINGER_S = 30


def ready(page) -> bool:
    # Community Cloud serves the app inside an iframe on its own page; check every frame.
    for frame in page.frames:
        try:
            if frame.locator("h1", has_text=READY).count():
                return True
        except Exception:  # noqa: BLE001 -- a frame can detach while the page reloads
            pass
    return False


def main(url: str) -> int:
    with sync_playwright() as p:
        # BROWSER_CHANNEL=msedge runs it locally on Windows without downloading Chromium.
        browser = p.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL") or None)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        start, woke = time.monotonic(), False
        while time.monotonic() - start < DEADLINE_S:
            if ready(page):
                state = "woken from sleep" if woke else "already awake"
                print(f"dashboard loaded ({state}) after {time.monotonic() - start:.0f} s")
                time.sleep(LINGER_S)
                browser.close()
                return 0
            button = page.get_by_role("button", name=WAKE)
            if not woke and button.count():
                print("asleep: clicking the wake-up button")
                button.first.click()
                woke = True
            time.sleep(5)
        page.screenshot(path="wake_failure.png", full_page=True)
        print(f"dashboard did not load within {DEADLINE_S} s; screenshot in wake_failure.png")
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
