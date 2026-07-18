import asyncio
import os
import json
import random
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import stealth_async

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
COOKIES_FILE = os.getenv("MUDAH_COOKIES_FILE", "/tmp/mudah_cookies.json")
MUDAH_EMAIL = os.getenv("MUDAH_EMAIL", "")
MUDAH_PASSWORD = os.getenv("MUDAH_PASSWORD", "")

BASE_URL = "https://www.mudah.my"
POST_AD_URL = f"{BASE_URL}/my/ads/new"

# Human-like delays (min, max) in ms — randomised to avoid bot detection
DELAY_SHORT = (500, 1500)
DELAY_MEDIUM = (1500, 3500)
DELAY_LONG = (3000, 6000)


async def _human_delay(delay_range: tuple[int, int] = DELAY_MEDIUM):
    """Sleep for a random duration within the given range to mimic human behaviour."""
    await asyncio.sleep(random.randint(*delay_range) / 1000)


# ---------------------------------------------------------------------------
# Cookie / Session helpers
# ---------------------------------------------------------------------------

async def _save_cookies(context: BrowserContext, path: str = COOKIES_FILE):
    """Persist browser cookies to disk so the next run can skip login."""
    cookies = await context.cookies()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[Mudah] Cookies saved → {path}")


async def _load_cookies(context: BrowserContext, path: str = COOKIES_FILE) -> bool:
    """Restore cookies from disk. Returns True if cookies were loaded."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"[Mudah] Cookies loaded ← {path}")
        return True
    except Exception as e:
        print(f"[Mudah] Cookie load failed: {e}")
        return False


async def _is_logged_in(page: Page) -> bool:
    """Quick heuristic: if the page shows 'Log Out' or the user avatar, we're logged in."""
    try:
        # Mudah.my typically shows a logout link or user menu when authenticated
        logout = await page.query_selector('[data-testid="logout"], a[href*="logout"], .user-menu')
        return logout is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------

async def _login(page: Page, email: str, password: str):
    """Perform email + password login on Mudah.my."""
    print("[Mudah] Navigating to login page...")
    await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=30_000)
    await _human_delay(DELAY_MEDIUM)

    # Mudah.my login form — selectors may shift; update if the site redesigns
    email_selector = 'input[name="email"], input[type="email"], #email'
    password_selector = 'input[name="password"], input[type="password"], #password'
    submit_selector = 'button[type="submit"], .login-btn, [data-testid="login-submit"]'

    # Fill email
    email_input = page.locator(email_selector).first
    await email_input.wait_for(state="visible", timeout=10_000)
    await email_input.click()
    await _human_delay(DELAY_SHORT)
    await email_input.fill(email)
    await _human_delay(DELAY_SHORT)

    # Fill password
    pw_input = page.locator(password_selector).first
    await pw_input.wait_for(state="visible", timeout=10_000)
    await pw_input.click()
    await _human_delay(DELAY_SHORT)
    await pw_input.fill(password)
    await _human_delay(DELAY_SHORT)

    # Submit
    await page.locator(submit_selector).first.click()
    await page.wait_for_load_state("networkidle", timeout=20_000)
    await _human_delay(DELAY_LONG)

    if await _is_logged_in(page):
        print("[Mudah] ✅ Login successful!")
        await _save_cookies(page.context)
    else:
        # Some sites use OTP / captcha — log a warning but don't crash
        print("[Mudah] ⚠️  Login may not have completed — check for CAPTCHA or OTP prompts.")
        print(f"[Mudah] Current URL: {page.url}")


# ---------------------------------------------------------------------------
# Human-like typing helper
# ---------------------------------------------------------------------------

async def _human_type(locator, text: str, delay_ms: int = 80):
    """Type text character-by-character with a small random delay per keystroke."""
    await locator.click()
    await asyncio.sleep(random.randint(*DELAY_SHORT) / 1000)
    for char in text:
        await locator.press(char)
        await asyncio.sleep(delay_ms / 1000 + random.uniform(0, delay_ms / 2000))


# ---------------------------------------------------------------------------
# Main automation
# ---------------------------------------------------------------------------

async def automate_mudah_post(
    title: str,
    description: str,
    price: str,
    image_paths: list[str] | None = None,
    category: str = "Properties",
    headless: bool = True,
):
    """
    End-to-end Mudah.my property listing automation.

    Parameters
    ----------
    title : str          – Catchy listing title (generated by LLM upstream).
    description : str    – Full listing description.
    price : str          – e.g. "RM 2500"
    image_paths : list   – Absolute paths to images on the host/container filesystem.
    category : str       – Mudah.my category name (default "Properties").
    headless : bool      – Run browser headlessly (True in Docker).
    """
    image_paths = image_paths or []

    print("\n" + "=" * 60)
    print("🤖 [Mudah Automator] Starting listing automation")
    print(f"   Title : {title}")
    print(f"   Price : {price}")
    print(f"   Images: {len(image_paths)}")
    print("=" * 60 + "\n")

    async with async_playwright() as p:
        # ---- Launch with stealth config ----
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="ms-MY",
            timezone_id="Asia/Kuala_Lumpur",
        )

        # Apply stealth — use async variant for async_playwright
        page = await context.new_page()
        await stealth_async(page)

        try:
            # ===== 1. SESSION RESTORE / LOGIN =====
            cookies_loaded = await _load_cookies(context)
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
            await _human_delay(DELAY_MEDIUM)

            if not cookies_loaded or not await _is_logged_in(page):
                if not MUDAH_EMAIL or not MUDAH_PASSWORD:
                    print("[Mudah] ❌ No credentials set (MUDAH_EMAIL / MUDAH_PASSWORD). "
                          "Skipping login — listing will NOT be posted.")
                    return {"status": "error", "message": "Missing Mudah.my credentials"}

                await _login(page, MUDAH_EMAIL, MUDAH_PASSWORD)
                if not await _is_logged_in(page):
                    return {"status": "error", "message": "Login failed — could not authenticate"}

            # ===== 2. NAVIGATE TO POST AD PAGE =====
            print("[Mudah] Navigating to Post Ad page...")
            await page.goto(POST_AD_URL, wait_until="domcontentloaded", timeout=30_000)
            await _human_delay(DELAY_LONG)

            # ===== 3. SELECT CATEGORY (if prompted) =====
            # Mudah.my may show a category picker first, or redirect to the form directly.
            # Try to find and click the "Properties" category.
            cat_locator = page.locator(f'a:has-text("{category}"), button:has-text("{category}")').first
            if await cat_locator.is_visible():
                print(f"[Mudah] Selecting category: {category}")
                await cat_locator.click()
                await _human_delay(DELAY_LONG)

            # ===== 4. FILL LISTING FORM =====
            print("[Mudah] Filling in listing details...")

            # --- Title ---
            title_field = page.locator(
                'input[name="title"], input[placeholder*="title" i], #ad_title, [data-testid="title-input"]'
            ).first
            if await title_field.is_visible():
                await _human_type(title_field, title)
            else:
                print("[Mudah] ⚠️  Title field not found — selector may need updating.")

            await _human_delay(DELAY_SHORT)

            # --- Description ---
            desc_field = page.locator(
                'textarea[name="description"], textarea[placeholder*="description" i], '
                '#ad_description, [data-testid="description-input"]'
            ).first
            if await desc_field.is_visible():
                await _human_type(desc_field, description, delay_ms=50)
            else:
                print("[Mudah] ⚠️  Description field not found — selector may need updating.")

            await _human_delay(DELAY_SHORT)

            # --- Price ---
            price_field = page.locator(
                'input[name="price"], input[placeholder*="price" i], #ad_price, [data-testid="price-input"]'
            ).first
            if await price_field.is_visible():
                await price_field.click()
                await _human_delay(DELAY_SHORT)
                # Strip "RM" prefix — Mudah usually wants a number only
                price_number = price.replace("RM", "").replace(",", "").strip()
                await price_field.fill(price_number)
            else:
                print("[Mudah] ⚠️  Price field not found — selector may need updating.")

            await _human_delay(DELAY_SHORT)

            # ===== 5. UPLOAD IMAGES =====
            if image_paths:
                print(f"[Mudah] Uploading {len(image_paths)} image(s)...")
                # Mudah.my typically has a file input or an upload button
                file_input = page.locator(
                    'input[type="file"], input[name*="image"], input[name*="photo"]'
                ).first
                if await file_input.count() > 0:
                    # Playwright supports multiple files on a single input
                    existing_paths = [p for p in image_paths if os.path.exists(p)]
                    if existing_paths:
                        await file_input.set_input_files(existing_paths)
                        # Wait for upload indicators to settle
                        await _human_delay(DELAY_LONG)
                        print(f"[Mudah] ✅ Uploaded {len(existing_paths)} image(s).")
                    else:
                        print("[Mudah] ⚠️  None of the image paths exist on disk.")
                else:
                    print("[Mudah] ⚠️  No file upload input found.")

            # ===== 6. SUBMIT =====
            print("[Mudah] Looking for submit button...")
            submit_btn = page.locator(
                'button:has-text("Post"), button:has-text("Submit"), '
                'button[type="submit"], [data-testid="submit-ad"]'
            ).first

            if await submit_btn.is_visible():
                await submit_btn.click()
                await page.wait_for_load_state("networkidle", timeout=30_000)
                await _human_delay(DELAY_LONG)

                # Check for success indicators
                final_url = page.url
                success_indicator = await page.query_selector(
                    '[data-testid="success"], .success-message, :text("Your ad has been")'
                )

                if success_indicator:
                    print(f"[Mudah] ✅ Ad posted successfully! URL: {final_url}")
                    return {"status": "success", "url": final_url}
                else:
                    print(f"[Mudah] ⚠️  Submit clicked but could not confirm success. URL: {final_url}")
                    return {"status": "success", "url": final_url, "note": "Submission unconfirmed"}
            else:
                print("[Mudah] ⚠️  Submit button not found — ad was NOT posted.")
                return {"status": "error", "message": "Submit button not found"}

        except Exception as e:
            print(f"[Mudah] ❌ Automation error: {e}")
            # Screenshot for debugging
            try:
                await page.screenshot(path="/tmp/mudah_error.png")
                print("[Mudah] Error screenshot saved → /tmp/mudah_error.png")
            except Exception:
                pass
            return {"status": "error", "message": str(e)}

        finally:
            # Save cookies regardless of outcome
            try:
                await _save_cookies(context)
            except Exception:
                pass
            await browser.close()


# ---------------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(automate_mudah_post(
        title="🔥 Beautiful Condo Near MRT — Fully Furnished",
        description="A stunning 2-bedroom condo with pool view, 5 min walk to MRT station...",
        price="RM 2500",
        image_paths=[],
        headless=False,
    ))
