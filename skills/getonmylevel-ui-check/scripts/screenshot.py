"""Screenshot a page at several viewport widths and report console errors.

    python screenshot.py URL [--widths 375 768 1280] [--out DIR] [--wait MS]

Requires Playwright for Python with a browser installed (``pip install
playwright`` and ``playwright install chromium``). The script does not install
anything. Without Playwright it prints what is missing and exits 3, so the
caller can fall back to another browser tool.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--widths", nargs="+", type=int, default=[375, 768, 1280])
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--out", default="ui-check-screenshots")
    parser.add_argument("--wait", type=int, default=500, help="milliseconds to wait after load")
    args = parser.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright for Python is not installed. Use another available browser tool, or ask the user "
              "before installing it (pip install playwright, then playwright install chromium).")
        return 3
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width in args.widths:
            page = browser.new_page(viewport={"width": width, "height": args.height})
            page.on("console", lambda message, w=width: problems.append(f"[{w}px] console {message.type}: {message.text}")
                    if message.type in ("error", "warning") else None)
            page.on("pageerror", lambda error, w=width: problems.append(f"[{w}px] page error: {error}"))
            page.goto(args.url, wait_until="networkidle")
            page.wait_for_timeout(args.wait)
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            if overflow:
                problems.append(f"[{width}px] page is wider than the viewport (horizontal scroll)")
            path = out / f"{width}.png"
            page.screenshot(path=str(path), full_page=True)
            print(f"Saved {path}")
            page.close()
        browser.close()
    print("\n".join(problems) if problems else "No console errors, page errors, or horizontal overflow.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
