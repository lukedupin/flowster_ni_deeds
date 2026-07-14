import os
import re

from django.core.files import File
from django.db import IntegrityError

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Request, \
    APIRouter
from fastapi.responses import Response, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from flowster import FlowSheet, FlowProfile, flowster_node, FlowExclude, \
    FlowsterChunk
from flowster.stdlib.ai.llm import chat, chat_stream, chat_result, list_models
from flowster.stdlib.ai import llm as ai_llm
import asyncio
import json
from flowster.core import util

from ni_deeds.models import Property
from ni_deeds.scrappers.resolve_address_name import resolve_owner_name
from ni_deeds.scrappers.deed_download import search_deeds
from ni_deeds.scrappers.deed_reader import read_deed

FLOW_PROFILE = None
SKIP = {}

def setup( settings ):
    global FLOW_PROFILE, SKIP
    FLOW_PROFILE = settings.FLOW_PROFILE
    SKIP = settings.SKIP

def gen_flow_sheet( header=None ):
    with open("chat_interface/meta.json") as handle:
        meta = json.load(handle)
        return FlowSheet(
            meta['title'],
            None,
            FLOW_PROFILE )

def _succ(**kwargs):
    return {"successful": True, **kwargs}

def _fail(**kwargs):
    return {"successful": False, **kwargs}

api_router = APIRouter()


@api_router.post("/clean_addresses")
async def clean_addresses(request: Request):
    body = await request.json()
    prompt: str = body.get('prompt', '')

    flow_sheet = gen_flow_sheet(request.headers)

    if (_ret := await chat(
        flow_sheet,
        prompt,
        system="""Return only a list of addresses as a markdown bulleted list.
Strip any city, state, and zip code from each address, keeping only the street address.
Do not include any other text or explanation.""",
    )).is_err():
        return _fail(reason=_ret.err_value)

    return _succ(addresses=_ret.ok_value)


@api_router.post("/process_address")
async def process_address(request: Request):
    body = await request.json()
    address: str = body.get('address', '')
    if not address:
        return _fail(reason="address is required")

    try:
        property = await Property.objects.acreate(initial_address=address)
    except IntegrityError:
        property = await Property.objects.aget(initial_address=address)

    # 1_resolve_address_name: find the property owner's name from the address
    found_name = await resolve_owner_name(address)
    if found_name is None:
        return _fail(reason=f"No owner found for address: {address}")

    property.found_name = found_name
    await property.asave()

    # 2_deed_download: download the deed PDF(s) recorded under the owner's name
    await search_deeds(found_name)

    dir_name = re.sub(r"[^a-z0-9]", "_", found_name.lower())
    download_dir = os.path.join(os.getcwd(), "pdfs", dir_name)
    pdf_names = sorted(
        name for name in os.listdir(download_dir) if name.lower().endswith(".pdf")
    ) if os.path.isdir(download_dir) else []
    if not pdf_names:
        return _fail(reason=f"No deeds found for: {found_name}")

    pdf_path = os.path.join(download_dir, pdf_names[0])
    with open(pdf_path, "rb") as handle:
        property.blob.save(pdf_names[0], File(handle), save=False)

    # 3_deed_reader: extract structured data from the downloaded deed PDF
    content = await read_deed(pdf_path, [address])
    property.content = content
    await property.asave()

    return _succ(property_id=property.id, found_name=found_name, content=content)


@api_router.get("/property/{uid}/pdf")
async def download_pdf(uid: str):
    property = await Property.getByUid(uid)
    if property is None:
        return _fail(reason=f"No property found for uid: {uid}")

    if not property.blob:
        return _fail(reason=f"No PDF found for uid: {uid}")

    with property.blob.open('rb') as handle:
        pdf_bytes = handle.read()

    filename = os.path.basename(property.blob.name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@api_router.get("/properties")
async def list_properties():
    properties = [prop.toJson() async for prop in Property.objects.all().order_by('initial_address')]
    return _succ(properties=properties)


@api_router.post("/chat")
async def property_chat(request: Request):
    body = await request.json()
    prompt: str = body.get('prompt', '')
    conversation: list = body.get('conversation', [])
    if not prompt:
        return _fail(reason="prompt is required")

    flow_sheet = gen_flow_sheet(request.headers)

    properties = [prop.toJson() async for prop in Property.objects.all().order_by('initial_address')]

    if (_stream := await chat_stream(
        flow_sheet,
        prompt,
        conversation=conversation,
        contexts={'PROPERTIES': properties},
        system="""Answer questions using only the property data provided in PROPERTIES.
If the answer isn't in PROPERTIES, say so instead of guessing.
Always respond in markdown.
Never return raw JSON.""",
    )).is_err():
        return _fail(reason=_stream.err_value)

    if (ret := await chat_result( flow_sheet, _stream.ok_value )).is_err():
        return _fail(reason=ret.err_value)

    return StreamingResponse(
        util.sse_stream( ret.ok_value, conversation ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


