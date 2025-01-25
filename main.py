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

"""
This script is mixing requests with playwright as I couldn't get the weird paging mechanism to work.

When you do `requests.get` on `docs_url`, you first get an error about enabling cookies.
If you use requests.Session(), it kinda works: 

 session = requests.Session()
 _ = requests.get(docs_url)
 r = session.post(docs_url,data=dict(resultRowBlockSize=10, offset=0)) 

however, the POST that a browser performs when you click "next page" has a bunch of extra stuff:
 docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&docPasswords=&passwordBox=false&offset=10&resultRowBlockSize=10&matrixColSpan=4&subParam=1&subReturnDsp=1&goHome=&show=thumbnail&applicationType=all&filter_propName=&filter_available=false&displayedDocIds=70028&selectFlags=false&displayedDocIds=70027&selectFlags=false&displayedDocIds=70026&selectFlags=false&displayedDocIds=70025&selectFlags=false&displayedDocIds=70024&selectFlags=false&displayedDocIds=70023&selectFlags=false&displayedDocIds=70022&selectFlags=false&displayedDocIds=70021&selectFlags=false&displayedDocIds=70020&selectFlags=false&orderBy_property=creationDate&orderBy_descendingRequested=true&dummy=
I couldn't really figure out which where necessary and it just seems to always return 
the first result page if you don'- get it right
 
"""

#%%"z

def get_pdf_from_page(page: str, fname_tag: str):
    soup = BeautifulSoup(page, "html.parser")

    # The page contains a bunch of hidden <input> elements,
    # the ones with name=pdfURI contain a slightly obfuscated way to get an url for downloading,
    # the ones with name=displayedDocsIds contain an (internal?) id of the document.
    # I didn't really try to get the displayed filename out of the page
    uri_elements = list(filter(lambda tag: tag.attrs["name"] == "pdfURI", soup.find_all("input")))
    id_elements = list(filter(lambda tag: tag.attrs["name"] == "displayedDocIds", soup.find_all("input")))

    # slight misnomer, these are the ids for requesting the content via POST.
    # Note: The uris seem to change when you reload the page. Much security...
    doc_uris = []
    for tag in uri_elements:
        # get the part after the "?"
        blob = tag.attrs["value"].split("?")[-1]
        # decode and find the part with id=<number>
        doc_id = re.match(r"id=(\d+)", base64.b64decode(blob).decode("utf8")).group(1)
        doc_uris.append(doc_id)

    doc_ids = [e.attrs["value"] for e in id_elements]

    Path("./downloads").mkdir(parents=True, exist_ok=True)

    for doc_uri, doc_id in tqdm(zip(doc_uris, doc_ids)):
        # clicking on the links with playwright didn't really work very well, the popup opened but never
        # filled with the content for some reason. But requests work fine
        r = requests.post(f"http://{PRINTER_IP}/DH/repository/content.pdf", data=dict(id=doc_uri, jt=2))
        assert r.status_code == 200
        with Path(f"./downloads/{fname_tag}_{doc_id}.pdf").open("wb") as outfile:
            outfile.write(r.content)

async def get_all_pdfs(playwright: Playwright, fname_tag: str) -> None:
    browser = await playwright.firefox.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    # It'll complain about cookies if we haven't visited the main page before
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