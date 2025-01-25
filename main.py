#%%
import base64
import itertools
import re
from pathlib import Path

from tqdm.auto import tqdm
import requests
from bs4 import BeautifulSoup
from playwright.async_api import Playwright, async_playwright
import asyncio

PRINTER_IP = "192.168.178.10"
docs_url = f"http://{PRINTER_IP}/web/guest/en/webdocbox/docListPage.cgi"


#%%


def get_pdf_from_page(page: str, fname_tag: str):
    soup = BeautifulSoup(page, "html.parser")

    uri_elements = list(filter(lambda tag: tag.attrs["name"] == "pdfURI", soup.find_all("input")))
    id_elements = list(filter(lambda tag: tag.attrs["name"] == "displayedDocIds", soup.find_all("input")))

    doc_uris = []
    for tag in uri_elements:
        blob = tag.attrs["value"].split("?")[-1]
        doc_id = re.match(r"id=(\d+)", base64.b64decode(blob).decode("utf8")).group(1)
        doc_uris.append(doc_id)

    doc_ids = [e.attrs["value"] for e in id_elements]

    Path("./downloads").mkdir(parents=True, exist_ok=True)
    for doc_uri, doc_id in tqdm(zip(doc_uris, doc_ids)):
        r = requests.post(f"http://{PRINTER_IP}/DH/repository/content.pdf", data=dict(id=doc_uri, jt=2))
        assert r.status_code == 200
        with Path(f"./downloads/{fname_tag}_{doc_id}.pdf").open("wb") as outfile:
            outfile.write(r.content)

async def get_all_pdfs(playwright: Playwright, fname_tag: str) -> None:
    browser = await playwright.firefox.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(f"http://{PRINTER_IP}")
    await page.goto(f"http://{PRINTER_IP}/web/guest/en/webdocbox/docListPage.cgi")
    for offset in itertools.count(start=0):
        content = await page.content()
        print(f"processing page {offset}...")
        get_pdf_from_page(content, fname_tag)
        button = page.get_by_role("link", name="Go to the next page.")
        if await button.count() == 0:
            break
        await button.click()
        await page.wait_for_load_state()

async def delete_all_documents(playwright: Playwright) -> None:
    browser = await playwright.firefox.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(f"http://{PRINTER_IP}")
    await page.goto(f"http://{PRINTER_IP}/web/guest/en/webdocbox/docListPage.cgi")
    for pagenr in itertools.count():
        boxes = await page.get_by_role("checkbox").all()
        if len(boxes) == 0:
            break
        for box in boxes:
            await box.check()
        print(f"processing page {pagenr}...")
        await page.get_by_role("link", name="Delete").click()
        await page.get_by_role("link", name="Delete File(s)").nth(1).click()
        await page.get_by_role("cell", name="OK").nth(3).click()
        await page.wait_for_load_state()


async def run():
    async with async_playwright() as playwright:
        await get_all_pdfs(playwright, "foo")
        #await delete_all_documents(playwright)

asyncio.run(run())