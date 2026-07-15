import os

from django.core.files import File
from django.utils import timezone

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

def _fail(reason, **kwargs):
    return {"successful": False, "reason": reason, **kwargs}

def _matches_search(prop: dict, search: str) -> bool:
    search = search.strip().lower()
    if not search:
        return True

    content = prop.get('content') or {}
    riders = content.get('riders') or []

    fields = [
        prop.get('found_name') or '',
        prop.get('initial_address') or '',
        content.get('loan_amount') or '',
        ', '.join(riders) if isinstance(riders, list) else riders,
        prop.get('timestamp_on') or '',
    ]
    return any(search in str(field).lower() for field in fields)

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
        return _fail(_ret.err_value)

    return _succ(addresses=_ret.ok_value)


def _sse(js: dict) -> str:
    return f"data: {json.dumps(js)}\n\n"


@api_router.post("/process_address")
async def process_address(request: Request):
    body = await request.json()
    address: str = body.get('address', '')

    progress_queue = asyncio.Queue()

    async def stream( progress_queue ):
        try:
            if not address:
                yield _sse({"type": "fail", **_fail("address is required")})
                return

            flow_sheet = gen_flow_sheet(request.headers)

            property = await Property.getOrCreate(address)

            async def _fail_log(reason, **kwargs):
                property.processing_log = reason
                await property.asave()
                return _fail(reason, **kwargs)

            # 1_resolve_address_name: find the property owner's name from the address
            if (_ret := await resolve_owner_name(flow_sheet, address)).is_err():
                return _sse({"type": "fail", **(await _fail_log(_ret.err_value))})
            found_name = _ret.ok_value
            await progress_queue.put( f"Found name: {found_name}")

            property.found_name = found_name
            await property.asave()

            # 2_deed_download: download the deed PDF(s) recorded under the owner's name
            if (_ret := await search_deeds(found_name, progress_queue)).is_err():
                return _sse({"type": "fail", **(await _fail_log(_ret.err_value))})
            download_dir = _ret.ok_value

            ############# Wrong shit AI code
            pdf_names = sorted(
                name for name in os.listdir(download_dir) if name.lower().endswith(".pdf")
            ) if os.path.isdir(download_dir) else []
            if not pdf_names:
                return _sse({"type": "fail", **(await _fail_log(f"No deeds found for: {found_name}"))})

            pdf_path = os.path.join(download_dir, pdf_names[0])
            with open(pdf_path, "rb") as handle:
                property.blob.save(pdf_names[0], File(handle), save=False)
            await property.asave()
            ##############

            # 3_deed_reader: extract structured data from the downloaded deed PDF
            if (_ret := await read_deed(flow_sheet, pdf_path, [address], progress_queue)).is_err():
                return _sse({"type": "fail", **(await _fail_log(_ret.err_value))})
            content = _ret.ok_value
            property.content = content
            property.processing_log = ""
            await property.asave()

            return _sse({"type": "succ", **_succ(property_id=property.id, found_name=found_name, content=content)})

        finally:
            await progress_queue.put(None)
    
    async def stream_with_progress():
        task = asyncio.create_task(stream(progress_queue))

        while True:
            try:
                message = progress_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if message is None:
                break
            yield _sse({"type": "progress", "message": message})

        yield _sse( await task )

    return StreamingResponse(
        stream_with_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@api_router.get("/property/{uid}/pdf")
async def download_pdf(uid: str):
    property = await Property.getByUid(uid)
    if property is None:
        return _fail(f"No property found for uid: {uid}")

    if not property.blob:
        return _fail(f"No PDF found for uid: {uid}")

    with property.blob.open('rb') as handle:
        pdf_bytes = handle.read()

    filename = os.path.basename(property.blob.name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@api_router.post("/property/{uid}/notes")
async def update_property_notes(uid: str, request: Request):
    property = await Property.getByUid(uid)
    if property is None:
        return _fail(f"No property found for uid: {uid}")

    body = await request.json()
    property.notes = body.get('notes', '')
    await property.asave()

    return _succ()


@api_router.post("/property/{uid}/delete")
async def delete_property(uid: str):
    property = await Property.getByUid(uid)
    if property is None:
        return _fail(f"No property found for uid: {uid}")

    property.deleted_on = timezone.now()
    await property.asave()

    return _succ()


@api_router.get("/properties")
async def list_properties():
    properties = [prop.toJson() async for prop in Property.objects.filter(deleted_on__isnull=True).order_by('initial_address')]
    return _succ(properties=properties)


@api_router.post("/chat")
async def property_chat(request: Request):
    body = await request.json()
    question: str = body.get('question', '')
    conversation: list = body.get('conversation', [])
    if not question:
        return _fail("question is required")

    flow_sheet = gen_flow_sheet(request.headers)

    search: str = request.query_params.get('search', '')
    all_properties = [prop.toJson() async for prop in Property.objects.filter(deleted_on__isnull=True).order_by('initial_address')]
    properties = [prop for prop in all_properties if _matches_search(prop, search)]

    if (_stream := await chat_stream(
        flow_sheet,
        question,
        conversation=conversation,
        contexts={'PROPERTIES': properties},
        system="""Answer questions using only the property data provided in PROPERTIES.
If the answer isn't in PROPERTIES, say so instead of guessing.
Always respond in markdown.
Never return raw JSON.""",
    )).is_err():
        return _fail(_stream.err_value)

    if (ret := await chat_result( flow_sheet, _stream.ok_value )).is_err():
        return _fail(ret.err_value)

    return StreamingResponse(
        util.sse_stream( ret.ok_value, conversation ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


