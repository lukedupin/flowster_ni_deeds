import asyncio
import base64
import os
import subprocess
import sys
import json

from flowster import FlowSheet, FlowProfile
from flowster.core import util
from flowster.tools.memory_agent import memory_agent
from result import Result, Ok, Err

STRUCTURE = {
    "owner": "the name of the property owner/grantee",
    "address": "The address of the property",
    "bank_name": "The name of the bank or lender",
    "loan_date": "The date the loan was issued. Called made on or security instrument date. Format to MM-DD-YYYY",
    "riders": "List of the checked/X'ed rider boxes on the deed",
    "loan_amount": "The loan amount, if present on the deed, as a string",
    "rider_section_found": "True if the rider setion of checkboxes was found on this page",
    "fha_loan": "Does this reference Federal Housing Administration (FHA) loan?",
}

SYSTEM_PROMPT = """You are reading a single page of a scanned property deed.
Look for the fields described in STRUCTURE on this page.
Leave a field unchanged in MEMORY if it isn't on this page.

Your job is data extraction. 
Your job is to extract and store any relevant information from the
images and contexts, and return it as a dictionary. 
If you don't have info, leave the field unchanged.
Never remove information from the MEMORY unless explicitly instructed to do so.
Always return a dictionary of relevant information, even if it's empty.
Use MEMORY as the current JSON, and STRUCTURE as the structure of the JSON (if provided).
The STRUCTURE provides detailed information about each field.
Return the entire MEMORY state with new information added.
"""

async def _progress(progress: asyncio.Queue | None, message: str) -> None:
    print(message)
    if progress is not None:
        await progress.put(message)

def pdf_to_images(pdf_path: str, dpi=150) -> str:
    pdf_path = os.path.abspath(pdf_path)
    work_dir = os.path.splitext(pdf_path)[0]
    os.makedirs(work_dir, exist_ok=True)

    print(f"Converting PDF to images: {pdf_path} -> {work_dir}")
    subprocess.run(
        [
            "gs", "-sDEVICE=png16m", f"-r{dpi}", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
            "-o", "page__%04d.png", pdf_path,
        ],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    print("Done converting PDF to images.")

    return work_dir


def image_to_base64(path: str) -> str:
    #print(f"Converting image to base64: {path}")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


async def read_deed(flow_sheet: FlowSheet, pdf_path: str, possible_addresses: list[str] = None, page_limit=-1, progress: asyncio.Queue | None = None) -> Result[dict, str]:
    try:
        work_dir = pdf_to_images(pdf_path, dpi=150)
    except subprocess.CalledProcessError as e:
        return Err(f"Failed to convert PDF to images: {e}")
    except OSError as e:
        return Err(f"Failed to convert PDF to images: {e}")

    page_names = sorted(name for name in os.listdir(work_dir) if name.startswith("page__"))
    await _progress(progress, f"Found {len(page_names)} page(s) to process.")
    if not page_names:
        return Err(f"No pages found in PDF: {pdf_path}")

    memory = {k: None for k in STRUCTURE.keys()}
    memory['riders'] = []
    contexts = {
        'POSSIBLE_ADDRESSES': possible_addresses or [],
    }

    for page_idx, page_name in enumerate(page_names):
        if page_limit > 0 and page_idx >= page_limit:
            break

        await _progress(progress, f"Processing {page_limit + 1} of {len(page_names)} {page_name}...")
        try:
            image = image_to_base64(os.path.join(work_dir, page_name))
        except OSError as e:
            await _progress(progress, f"  {page_name}: error - {e}")
            continue
        #print(len(image))

        result = await memory_agent(
            flow_sheet,
            """Only fill out the address if it is found in the page.
Prefer null address if none is found.
If no bank is found, prefer null bank.
If no loan amount is found, prefer null loan amount.
If no riders are found, prefer null riders.""",
            system=SYSTEM_PROMPT,
            contexts=contexts,
            memory=memory,
            data=STRUCTURE,
            images=[image],
            credentials='process',
        )
        if result.is_err():
            await _progress(progress, f"  {page_name}: error - {result.err_value}")
            continue

        for k,v in result.ok_value.items():
            if k == 'riders':
                if len(ary := util.xlist(v)) > 0:
                    memory[k] = ary
            if k == "rider_section_found":
                if util.xbool(v) and 'rider_page' not in memory:
                    memory['rider_section_found'] = True
                    memory['rider_page'] = page_name
            if k == "fha_loan":
                if util.xbool(v) and 'fha_page' not in memory:
                    memory['fha_loan'] = True
                    memory['fha_page'] = page_name
            elif v is not None:
                memory[k] = v
        await _progress(progress, f"  {page_name}: memory now {memory}")

        if all(memory.get(field) for field in STRUCTURE.keys()):
            await _progress(progress, f"  All fields found by {page_name}, stopping early.")
            break

    return Ok(memory)


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python 3_deed_reader.py <pdf_path> [possible_address]")
        sys.exit(1)

    profile = FlowProfile({
        'llm': {
            'default': {
                'type': 'ollama',
                'model_name': 'gpt-oss-gpu-large',
                'streaming': True,
            },
            'vision': {
                'type': 'ollama',
                'model_name': 'mistral-small3.2',
                'streaming': True,
            },
        }
    })
    flow_sheet = FlowSheet("DeedReader", None, profile)

    pdf_path = sys.argv[1]
    possible_addresses = sys.argv[2:]
    print(f"Starting deed read: {pdf_path}")
    result = await read_deed(flow_sheet, pdf_path, possible_addresses)
    if result.is_err():
        print(f"⚠️  {result.err_value}")
        sys.exit(1)

    print("Final extracted data:")
    print(json.dumps(result.ok_value, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
