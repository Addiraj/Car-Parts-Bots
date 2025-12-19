"""
Playwright-based extractor for PartsNumber.

Usage (Windows CMD):
  set PN_USERNAME=testhajj
  set PN_PASSWORD=avvha123
  set PN_BASE_URL=https://login.partsnumber.com
  set OUTPUT_CSV=F:\\Car-Parts-Bot\\data\\parts_pn.csv
  python -m scripts.extract_partsnumber --mode makes --makes Toyota --models Corolla --years 2018

First time only:
  python -m playwright install chromium
"""
import os
import csv
import time
import argparse
from pathlib import Path
from typing import List
from playwright.sync_api import sync_playwright, BrowserContext


def login_and_get_context(pw, headless: bool = True) -> BrowserContext:
    base_url = os.getenv("PN_BASE_URL", "https://login.partsnumber.com").rstrip("/")
    username = os.getenv("PN_USERNAME")
    password = os.getenv("PN_PASSWORD")
    if not username or not password:
        raise RuntimeError("PN_USERNAME and PN_PASSWORD must be set in environment")

    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=".pn_state.json" if Path(".pn_state.json").exists() else None)
    page = context.new_page()
    page.goto(base_url, wait_until="load")

    # Try to detect and fill login form with retries (handle redirects)
    for _ in range(3):
        try:
            # Wait briefly for either dashboard or login inputs
            page.wait_for_timeout(600)
            # Prefer explicit IDs seen in DOM: #username and #password
            login_user = page.locator("#username, input[name='username'], input[type='text']").first
            login_pass = page.locator("#password, input[type='password']").first
            if login_pass.count() > 0:
                if login_user.count() == 0:
                    # Some pages use email/phone input with type=email
                    login_user = page.locator("input[type='email'], input[name='login'], input[name='email']").first
                # Fill creds
                if login_user.count() > 0:
                    login_user.fill(username)
                login_pass.fill(password)
                # Click login/submit
                btn = page.locator("button[type='submit'], button:has-text('Login'), button:has-text('Sign in'), input[type='submit']").first
                if btn.count() > 0:
                    btn.click()
                else:
                    login_pass.press("Enter")
                page.wait_for_load_state("networkidle")
                time.sleep(800/1000)
                break
            else:
                # Maybe already signed in
                break
        except Exception:
            # Navigation may invalidate context; just continue loop
            continue

    # Save session for next runs
    context.storage_state(path=".pn_state.json")
    return context


def write_rows(output_csv: str, rows: List[dict]):
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "part_number",
        "name",
        "brand",
        "price",
        "quantity_min",
        "make",
        "model",
        "year",
    ]
    exists = Path(output_csv).exists()
    with open(output_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def extract_by_search(page, query: str) -> List[dict]:
    """Example: type a part name into the search and collect top results.
    Note: Selectors likely need to be adjusted for real markup.
    """
    rows: List[dict] = []
    # Ensure we are on a page that exposes a global search; try clicking nav if needed
    nav_try = page.locator("a:has-text('Search'), a:has-text('Catalog'), a:has-text('Parts')").first
    if nav_try.count() > 0:
        try:
            nav_try.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
        except Exception:
            pass

    # Search box near the top; try multiple patterns with explicit wait
    search_selectors = [
        "input[placeholder*='catalog' i]",
        "input[placeholder*='vin' i]",
        "input[placeholder*='search' i]",
        "input[type='search']",
        "[role='search'] input",
    ]
    search_box = page.locator(", ".join(search_selectors)).first
    if search_box.count() == 0:
        try:
            page.wait_for_selector(", ".join(search_selectors), timeout=15000)
            search_box = page.locator(", ".join(search_selectors)).first
        except Exception:
            # Try focusing the page and typing CTRL/ to focus global search if site supports
            try:
                page.keyboard.press("Control+K")
                page.wait_for_timeout(500)
                search_box = page.locator(", ".join(search_selectors)).first
            except Exception:
                pass
    if search_box.count() == 0:
        return rows
    search_box.click()
    search_box.fill(query)
    search_box.press("Enter")
    page.wait_for_load_state("networkidle")
    time.sleep(1)

    # Collect items - adjust selectors to match real results list
    items = page.locator(".result, .part-item, .card, [data-testid='result-card']").all()
    for it in items[:50]:
        name = it.locator(".name, .title").first.text_content() or ""
        part_number = it.locator(".sku, .part-number").first.text_content() or ""
        brand = it.locator(".brand").first.text_content() or ""
        price = it.locator(".price").first.text_content() or ""
        rows.append({
            "part_number": part_number.strip(),
            "name": name.strip(),
            "brand": brand.strip(),
            "price": price.strip(),
            "quantity_min": "",
            "make": "",
            "model": "",
            "year": "",
        })
    return rows


def _select_dropdown_value(page, label_texts: List[str], value: str) -> bool:
    """
    Attempt to select a value in a dropdown associated with any of the given labels.
    Tries common patterns: label + select, aria-label, role=combobox, data attributes.
    Returns True if selection interaction likely succeeded.
    """
    if not value:
        return True
    # Normalize search text
    value_norm = value.strip().lower()
    # 1) Try <label>Text</label><select> pattern
    for label_text in label_texts:
        label = page.locator(f"label:has-text('{label_text}')").first
        if label.count() > 0:
            # Try a following select
            sel = label.locator("xpath=following::select[1]").first
            if sel.count() == 0:
                # Or within the same container
                sel = label.locator("..").locator("select").first
            if sel.count() > 0:
                try:
                    # Try exact option match first
                    sel.select_option(label=value)
                except Exception:
                    # Fallback: select by text content (case-insensitive)
                    options = sel.locator("option")
                    count = options.count()
                    for i in range(count):
                        txt = (options.nth(i).text_content() or "").strip()
                        if txt.lower() == value_norm:
                            sel.select_option(index=i)
                            break
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
                return True
    # 2) Try aria-label/select[name]
    for label_text in label_texts:
        sel = page.locator(f"select[aria-label*='{label_text}' i], select[name*='{label_text}' i]").first
        if sel.count() > 0:
            try:
                sel.select_option(label=value)
            except Exception:
                options = sel.locator("option")
                count = options.count()
                for i in range(count):
                    txt = (options.nth(i).text_content() or "").strip()
                    if txt.lower() == value_norm:
                        sel.select_option(index=i)
                        break
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            return True
    # 3) Try comboboxes
    for label_text in label_texts:
        combobox = page.locator(f"[role='combobox'][aria-label*='{label_text}' i], [role='combobox'][aria-labelledby*='{label_text}' i]").first
        if combobox.count() > 0:
            combobox.click()
            # Type to filter and press Enter
            page.keyboard.type(value)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            return True
    # 4) Inputs with datalist
    for label_text in label_texts:
        input_el = page.locator(f"input[list][aria-label*='{label_text}' i]").first
        if input_el.count() > 0:
            input_el.fill(value)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            return True
    return False


def extract_by_make_model_years(page, makes: List[str], models: List[str], years: List[str]) -> List[dict]:
    """
    Navigate Make/Model/Year filters, then scrape results.
    Since exact selectors may differ, this function tries several reasonable patterns.
    """
    rows: List[dict] = []
    # Ensure we are on a page that has filters/search
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(600)

    # If site has a dedicated MMY page, try common nav anchors
    possible_nav = page.locator("a:has-text('Catalog'), a:has-text('Parts'), a:has-text('Search')").first
    if possible_nav.count() > 0:
        try:
            possible_nav.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(400)
        except Exception:
            pass

    # Iterate combinations; if some list is empty, use [''] to no-op that level
    makes_list = makes or [""]
    models_list = models or [""]
    years_list = years or [""]

    for make in makes_list:
        _select_dropdown_value(page, ["Make", "Brand", "Manufacturer"], make)
        for model in models_list:
            _select_dropdown_value(page, ["Model"], model)
            for year in years_list:
                _select_dropdown_value(page, ["Year", "Production Year"], year)

                # Trigger search if there is a button
                search_btn = page.locator("button:has-text('Search'), button:has-text('Find'), button[type='submit']").first
                if search_btn.count() > 0:
                    try:
                        search_btn.click()
                    except Exception:
                        pass

                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(600)

                # Collect results - try table and card/grid patterns
                # 1) Table rows
                result_rows = page.locator("table tbody tr")
                if result_rows.count() == 0:
                    # 2) Cards
                    result_rows = page.locator(".result, .part-item, .card, [data-testid='result-card']")

                count = min(100, result_rows.count())
                for i in range(count):
                    it = result_rows.nth(i)
                    # Try various selectors within a row/card
                    name = (it.locator(".name, .title, [data-field='name']").first.text_content() or "").strip()
                    part_number = (it.locator(".sku, .part-number, [data-field='partNumber'], td:has-text('#')").first.text_content() or "").strip()
                    brand = (it.locator(".brand, [data-field='brand']").first.text_content() or "").strip()
                    price = (it.locator(".price, [data-field='price'], td:has(.currency)").first.text_content() or "").strip()
                    qty = (it.locator(".quantity, .qty, [data-field='minQty']").first.text_content() or "").strip()

                    rows.append({
                        "part_number": part_number,
                        "name": name,
                        "brand": brand,
                        "price": price,
                        "quantity_min": qty,
                        "make": make or "",
                        "model": model or "",
                        "year": year or "",
                    })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["search", "makes"], default="search")
    parser.add_argument("--query", help="search text", default="Alternator")
    parser.add_argument("--makes", nargs="*", default=[])
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument("--years", nargs="*", default=[])
    parser.add_argument("--output", default=os.getenv("OUTPUT_CSV", "data/parts_pn.csv"))
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    with sync_playwright() as pw:
        context = login_and_get_context(pw, headless=not args.headful)
        page = context.new_page()
        page.goto(os.getenv("PN_BASE_URL", "https://login.partsnumber.com"), wait_until="domcontentloaded")

        all_rows: List[dict] = []
        if args.mode == "search":
            all_rows.extend(extract_by_search(page, args.query))
        else:
            all_rows.extend(
                extract_by_make_model_years(
                    page=page,
                    makes=args.makes,
                    models=args.models,
                    years=args.years,
                )
            )

        if all_rows:
            write_rows(args.output, all_rows)
            print(f"Wrote {len(all_rows)} rows to {args.output}")
        else:
            print("No rows extracted. Adjust selectors or queries.")

        context.close()


if __name__ == "__main__":
    main()


