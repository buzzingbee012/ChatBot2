import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print("Navigating to https://www.allindiachat.com/ ...")
            await page.goto("https://www.allindiachat.com/")
            await page.wait_for_timeout(5000)
            
            content = await page.content()
            with open("site_dump.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Dumped HTML to site_dump.html")
            
            # also screenshot just in case
            await page.screenshot(path="site_preview.png")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
