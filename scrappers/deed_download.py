import asyncio
import os
import re
import shutil
import sys

import cv2
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from result import Result, Ok, Err

TEMPLATE_PATH = os.path.join(os.getcwd(), "ni_deeds", "template.png")


async def _progress(progress: asyncio.Queue | None, message: str) -> None:
    print(message)
    if progress is not None:
        await progress.put(message)


async def click_template_matches(page, screenshot_path: str, template_path: str, threshold=0.8, progress: asyncio.Queue | None = None) -> bool:
    screenshot = cv2.imread(screenshot_path)
    template = cv2.imread(template_path)
    th, tw = template.shape[:2]

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, best_val, _, (x, y) = cv2.minMaxLoc(result)
    await _progress(progress, f"Best match: {best_val * 100:.1f}% at ({x}, {y})")
    if best_val < threshold:
        return False

    center_x, center_y = x + tw // 2, y + th // 2
    await _progress(progress, f"  Clicking center ({center_x}, {center_y})")
    await page.mouse.click(center_x, center_y)

    marked = screenshot.copy()
    cv2.circle(marked, (center_x, center_y), 20, (0, 0, 255), 3)
    cv2.imwrite("page_click.png", marked)
    return True


async def download_document(page, instruments: set, progress: asyncio.Queue | None = None) -> str | None:
    await page.wait_for_selector("#cphNoMargin_ImageViewer1_ifrLTViewer")
    await _progress(progress, "Waiting for download link #cphNoMargin_OptionsBar1_lnkDld...")
    await page.wait_for_selector("#cphNoMargin_OptionsBar1_lnkDld")
    await asyncio.sleep(2)

    instrument = (await page.locator("[id$='txtInstrumentNo']").inner_text()).strip()
    await _progress(progress, f"  Instrument number: {instrument}")
    if instrument in instruments:
        await _progress(progress, f"  Instrument {instrument} already downloaded, skipping.")
        return None
    instruments.add(instrument)

    iframe = None
    for attempt in range(1, 4):
        await page.click("#cphNoMargin_OptionsBar1_lnkDld")
        await _progress(progress, "Clicked download link, waiting for option window iframe...")

        await asyncio.sleep(2)

        iframe = page.frame_locator("#ifrOptionWindow")
        await iframe.locator("#btnProcessNow").wait_for()
        await _progress(progress, "Found #btnProcessNow in ifrOptionWindow, clicking...")
        await iframe.locator("#btnProcessNow").click()

        await _progress(progress, f"Waiting for PDF window iframe #ifrPDFWindow (attempt {attempt}/3)...")
        try:
            await iframe.locator("#ifrPDFWindow").wait_for(timeout=3000)
            break
        except PlaywrightTimeoutError:
            await _progress(progress, "  Timed out waiting for ifrPDFWindow, closing and retrying...")
            await page.locator("img[alt='Close']").click()
    else:
        print("ifrPDFWindow never appeared after 3 attempts")
        return None

    src = await iframe.locator("#ifrPDFWindow").get_attribute("src")
    await _progress(progress, f"  ifrPDFWindow src: {src}")

    for attempt in range(1, 4):
        await asyncio.sleep(2)

        screenshot_path = "page.png"
        await _progress(progress, f"Saving screenshot to {screenshot_path}...")
        await page.screenshot(path=screenshot_path)
        if await click_template_matches(page, screenshot_path, TEMPLATE_PATH, progress=progress):
            break
    else:
        await _progress(progress, "Template match not found after 3 attempts, continuing...")

    pdf_url = f"https://recorder.kcgov.us{src}"

    await _progress(progress, "Looking for Close image...")
    await page.locator("img[alt='Close']").click()

    return pdf_url


async def find_pdf_urls(page, name: str, progress: asyncio.Queue | None = None) -> list[str]:
    url = "https://recorder.kcgov.us/RealEstate/SearchEntry.aspx"
    pdf_urls = []

    await _progress(progress, "Loading search page...")
    await page.goto(url)
    await page.wait_for_load_state("networkidle")

    await _progress(progress, f"Checking deed type and entering name... {name}")
    await page.check("#cphNoMargin_f_dclDocType_9")
    await page.fill("#cphNoMargin_f_txtParty", name)
    async with page.expect_navigation(wait_until="networkidle"):
        await page.keyboard.press("Enter")
    await _progress(progress, f"Search results loaded: {page.url}")

    td = page.locator(".fauxDetailLink").last
    await _progress(progress, "Clicking last fauxDetailLink...")
    async with page.expect_navigation(wait_until="load"):
        await td.click()
    await _progress(progress, f"Detail page loaded: {page.url}")

    # Rewind to the starting document since we might be in the middle
    try:
        for _ in range(100):
            await asyncio.sleep(1)
            prev_img = page.locator("#OptionsBar1_imgPrev")
            if await prev_img.evaluate("el => el.hasAttribute('disabled')"):
                break

            await prev_img.click()
            await asyncio.sleep(2)

    except PlaywrightTimeoutError as e:
        print(f"Timed out searching deeds for {name}: {e}")
    except Exception as e:
        print(f"Failed to search deeds for {name}: {e}")

    instruments = set()

    # Now we click through and save each file
    for _ in range(100):
        try:
            pdf_url = await download_document(page, instruments, progress)
            if pdf_url is not None:
                pdf_urls.append(pdf_url)

            prev_img = page.locator("#OptionsBar1_imgNext")
            is_disabled = await prev_img.evaluate("el => el.hasAttribute('disabled')")
            if not is_disabled:
                await asyncio.sleep(1)
                await _progress(progress, "OptionsBar1_imgNext is enabled, looping back for next record...")
                await prev_img.click()
                await asyncio.sleep(2)
                continue

            # We are done
            await _progress(progress, f"OptionsBar1_imgNext is disabled, found {len(pdf_urls)} PDF URLs.")
            break

        except PlaywrightTimeoutError as e:
            print(f"Timed out searching deeds for {name}: {e}")
            await _progress(progress, "Looking for Close image...")
            await page.locator("img[alt='Close']").click()
        except Exception as e:
            print(f"Failed to search deeds for {name}: {e}")
            await _progress(progress, "Looking for Close image...")
            await page.locator("img[alt='Close']").click()

    return pdf_urls


async def process_pdf_urls(page, pdf_url, progress: asyncio.Queue | None = None) -> None:
    await _progress(progress, f"  Opening new tab: {pdf_url}")
    await page.goto(pdf_url)
    await page.wait_for_load_state("load")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
    await _progress(progress, "  PDF tab loaded.")

    screenshot_path = "page.png"
    await _progress(progress, f"Saving screenshot to {screenshot_path}...")
    await page.screenshot(path=screenshot_path)

    await click_template_matches(page, screenshot_path, TEMPLATE_PATH, progress=progress)


async def screenshot_loop() -> None:
    screenshot_path = os.path.join(os.getcwd(), "./dist/assets/screenshot.png")
    try:
        while True:
            proc = await asyncio.create_subprocess_exec(
                "import", "-display", ":99", "-window", "root", screenshot_path,
            )
            await proc.wait()
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass


def add_pdf_extension(directory: str) -> None:
    for filename in os.listdir(directory):
        path = os.path.join(directory, filename)
        if os.path.isfile(path) and not filename.lower().endswith(".pdf"):
            os.rename(path, path + ".pdf")


async def search_deeds(name: str, progress: asyncio.Queue | None = None) -> Result[str, str]:
    dir_name = re.sub(r"[^a-z0-9]", "_", name.lower())
    download_dir = os.path.join(os.getcwd(), "pdfs", dir_name)

    try:
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)
        os.makedirs(download_dir)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, downloads_path=download_dir) #, args=["--headless=new"])

            try:
                page = await browser.new_page()
                timer_task = asyncio.create_task(screenshot_loop())

                pdf_urls = await find_pdf_urls(page, name, progress)
                #input("Press Enter to process PDF URLs...")
                await _progress(progress, f"Found {len(pdf_urls)} PDF URLs.")
                for pdf_url in pdf_urls:
                    pass #await process_pdf_urls(page, pdf_url, progress)

                #input("Press Enter to close browser...")
            finally:
                timer_task.cancel()
                await timer_task
                await browser.close()

        add_pdf_extension(download_dir)

    except PlaywrightTimeoutError as e:
        return Err(f"Timed out searching deeds for {name}: {e}")
    except Exception as e:
        return Err(f"Failed to search deeds for {name}: {e}")

    return Ok(download_dir)


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python 2_deed_download.py <name>")
        sys.exit(1)

    name = " ".join(sys.argv[1:])
    print(f"Searching deeds for: {name}")
    result = await search_deeds(name)
    if result.is_err():
        print(f"⚠️  {result.err_value}")
        sys.exit(1)

    print(f"Saved deeds to: {result.ok_value}")


if __name__ == "__main__":
    asyncio.run(main())
