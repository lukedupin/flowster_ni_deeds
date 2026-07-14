import asyncio
import base64
import os
import subprocess
import sys
import json

from flowster import FlowSheet, FlowProfile
from flowster.core import util
from flowster.tools.memory_agent import memory_agent

STRUCTURE = {
    "owner": "the name of the property owner/grantee",
    "address": "The address of the property",
    "bank_name": "The name of the bank or lender",
    "riders": "List of the checked/X'ed rider boxes on the deed",
    "loan_amount": "The loan amount, if present on the deed, as a string",
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


def pdf_to_images(pdf_path: str) -> str:
    pdf_path = os.path.abspath(pdf_path)
    work_dir = os.path.splitext(pdf_path)[0]
    os.makedirs(work_dir, exist_ok=True)

    print(f"Converting PDF to images: {pdf_path} -> {work_dir}")
    subprocess.run(
        [
            "gs", "-sDEVICE=png16m", "-r150", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
            "-o", "page__%04d.png", pdf_path,
        ],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    print("Done converting PDF to images.")

    return work_dir


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


async def read_deed(pdf_path: str) -> dict:
    work_dir = pdf_to_images(pdf_path)
    page_names = sorted(name for name in os.listdir(work_dir) if name.startswith("page__"))
    print(f"Found {len(page_names)} page(s) to process.")

    profile = FlowProfile({
        'llm': {
            'default': {
                'type': 'ollama',
                'model_name': 'mistral-small3.2',
                'streaming': True,
            }
        }
    })
    flow_sheet = FlowSheet("DeedReader", None, profile)

    memory = {k: None for k in STRUCTURE.keys()}
    memory['riders'] = []
    contexts = {
        'POSSIBLE_ADDRESSES': [sys.argv[2:] if len(sys.argv) > 2 else ""],
    }

    for page_name in page_names:
        print(f"Processing {page_name}...")
        image = image_to_base64(os.path.join(work_dir, page_name))

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
        )
        if result.is_err():
            print(f"  {page_name}: error - {result.err_value}")
            continue

        for k,v in result.ok_value.items():
            if k == 'riders':
                if len(ary := util.xlist(v)) > 0:
                    memory[k] = ary
            elif v is not None:
                memory[k] = v
        print(f"  {page_name}: memory now {memory}")

        if all(memory.get(field) for field in STRUCTURE.keys()):
            print(f"  All fields found by {page_name}, stopping early.")
            break

    return memory


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python 3_deed_reader.py <pdf_path> [possible_address]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Starting deed read: {pdf_path}")
    data = await read_deed(pdf_path)
    print("Final extracted data:")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
