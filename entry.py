import base64
import os, django
from pathlib import Path
import shutil
import subprocess
from typing import AsyncGenerator, Awaitable, Coroutine

from asgiref.sync import sync_to_async
from starlette.staticfiles import StaticFiles

from flowster.tools.memory_agent import memory_agent
from flowster.core.util import context_to_kwargs, sse_stream, is_https_url, embed_url_contents

from chat_interface.models.chat_session import ChatSession
from chat_interface.models.prompt import Prompt

import uuid
import sys
import re
import aiohttp
import ffmpeg
import fitz  # PyMuPDF

import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Request, \
    APIRouter
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from flowster import FlowSheet, FlowProfile, flowster_node, FlowExclude, \
    FlowsterChunk
from flowster.stdlib import media
from flowster.stdlib.ai.llm import chat_stream, chat_result, list_models, list_thinking
from flowster.stdlib.ai import llm as ai_llm
import asyncio
import json
import requests
from datetime import datetime
import time
from flowster.core import util

from flowster.stdlib.storage import cache, filesystem

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

api_router = APIRouter()
ws_router = APIRouter()

@api_router.post("/chat")
async def chat(request:Request):#question: str=Body(...), conversation: list[dict]=Body(...)):
    body = await request.json()
    chat_session_uid: str = body.get('chat_session_uid', None)
    question: str = body.get('question', '')
    conversation: list[dict] = body.get('conversation', [])
    contexts: list[dict] = body.get('contexts', [])
    model: str = body.get('model', None)
    thinking = body.get('thinking', None)

    flow_sheet = gen_flow_sheet(request.headers)

    images = [x['content'] for x in contexts if x['file_type'] == 'image']
    contexts = [x for x in contexts if x['file_type'] != 'image']

    sse_messages = {}

    # Track which contexts are URLs, so we can push their converted markdown back to the client
    url_context_names = [ctx['name'] for ctx in contexts if is_https_url(ctx.get('content', ''))]

    # Add variable params
    kwargs = context_to_kwargs( contexts )

    if url_context_names:
        sse_messages['update_contexts'] = {
            name: kwargs['contexts'][name]
            for name in url_context_names if name in kwargs.get('contexts', {})
        }

    # Store the model if its changed
    if model is not None and model != "":
        await filesystem.write(flow_sheet, f"model", model)

    # Get or create the chat session
    chat_sess = await ChatSession.getOrCreateByUid(chat_session_uid, question[:64] )

    # Add the user's question
    await Prompt.create( type=Prompt.TYPE_USER, chat_session=chat_sess, content=question )

    # If a MEMORY context was supplied, let the memory agent handle it first
    if "MEMORY" in kwargs.get('contexts', {}):
        ctx = kwargs['contexts']
        memory_ctx = ctx.get("MEMORY", {})
        structure_ctx = ctx.get("STRUCTURE", {})

        # Build the call to the async memory agent
        # (you can add more kwargs here if needed)
        mem_result = await memory_agent(
            flow_sheet=flow_sheet,
            question=question,
            memory=memory_ctx,
            structure=structure_ctx,
            conversation=conversation,
            conversation_config=1,
            model=model,
        )

        # Store the memory agent’s output back into the MEMORY context
        if mem_result.is_ok():
            kwargs['contexts']["MEMORY"] = mem_result.ok_value
            if 'update_contexts' not in sse_messages:
                sse_messages['update_contexts'] = {}
            sse_messages['update_contexts']['MEMORY'] = mem_result.ok_value
        else:
            print("Memory agent error:", mem_result.err_value)

        print("Memory agent result:", mem_result.ok_value if mem_result.is_ok() else mem_result.err_value)



    # Endpoint that returns a single response
    if (_stream := await chat_stream(
        flow_sheet,
        question,
        conversation=conversation,
        tools=[],
        images=images,
        model=model,
        **kwargs
    )).is_err():
        return {"error": _stream.err_value}
    stream = _stream.ok_value

    # Create the streamer
    if (ret := await chat_result( flow_sheet, stream )).is_err():
        return {"error": ret.err_value}

    await sync_to_async( Prompt.objects.create )(
        chat_session=chat_sess,
        type=Prompt.TYPE_USER,
        content=question,
    )

    # Create my system prompt
    assistant = Prompt(chat_session=chat_sess, type=Prompt.TYPE_ASSISTANT)


    async def save_chat( chunk ):
        if chunk is None:
            await sync_to_async(assistant.save)()

        elif chunk.type == 'full_content':
            assistant.content = chunk.text

        elif chunk.type == 'full_thinking':
            assistant.extra['thinking'] = chunk.text


    """Endpoint that streams events using SSE"""
    return StreamingResponse(
        sse_stream( ret.ok_value, conversation, save_chat, **sse_messages ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@api_router.post("/model")
async def _model(request:Request):
    body = await request.json()
    model: str = body.get('model', None)

    flow_sheet = gen_flow_sheet(request.headers)

    if model is None or model == '':
        model = None
        if (_model := await filesystem.read(flow_sheet, f"model")).is_ok():
            if _model.ok_value is not None and _model.ok_value != '':
                model = _model.ok_value

    else:
        if (ret := await filesystem.write(flow_sheet, f"model", model)).is_err():
            return {"successful": False, "reason": ret.err_value}

        # update the order to put this at the top
        if (_model_list := await filesystem.read(flow_sheet, f"model_list")).is_ok():
            model_lookup = _model_list.ok_value
            if model in model_lookup:
                largest = -1
                for val in model_lookup.values():
                    largest = max(largest, val)
                if model_lookup[model] < largest:
                    model_lookup[model] = largest + 1
                if (ret := await filesystem.write(flow_sheet, f"model_list", model_lookup)).is_err():
                    return {"successful": False, "reason": ret.err_value}

    return {"successful": True, "model": model}


def _pdf_to_img_fitz(pdf_bytes: bytes, height: int) -> list[str]:
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        zoom = height / page.rect.height
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        images.append(base64.b64encode(pix.tobytes("png")).decode('ascii'))
    doc.close()
    return images


def _pdf_to_img_ghostscript(pdf_bytes: bytes) -> list[str]:
    work_dir = os.path.join("/tmp/pdf_to_img", str(uuid.uuid4()))
    os.makedirs(work_dir, exist_ok=True)

    try:
        pdf_path = os.path.join(work_dir, "input.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        subprocess.run(
            [
                "gs", "-sDEVICE=png16m", "-r150", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
                "-o", "page__%04d.png", pdf_path,
            ],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

        images = []
        for name in sorted(os.listdir(work_dir)):
            if not name.startswith("page__"):
                continue
            with open(os.path.join(work_dir, name), "rb") as f:
                images.append(base64.b64encode(f.read()).decode('ascii'))
        return images
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@api_router.post("/pdf_to_img")
async def pdf_to_img(request: Request):
    pdf_bytes = await request.body()

    if not pdf_bytes:
        return {"error": "pdf is required"}

    try:
        images = _pdf_to_img_ghostscript(pdf_bytes)
    except Exception as e:
        return {"error": f"Failed to convert pdf: {e}"}

    return {"successful": True, "images": images}


@api_router.post("/expand_content")
async def expand_content(request: Request):
    body = await request.json()
    context = body.get('context', '')
    if not context:
        return {"error": "context is required"}
    try:
        content = embed_url_contents(context)
    except Exception as e:
        return {"successful": False, "reason": f"Failed to expand content: {e}"}
    return {"successful": True, "content": content}


@api_router.get("/tags")
async def get_tags( request: Request):
    flow_sheet = gen_flow_sheet(request.headers)

    if (_ret := await list_models(flow_sheet)).is_err():
        return {"error": _ret.err_value}
    models = _ret.ok_value

    if (_model_list := await filesystem.read(flow_sheet, f"model_list")).is_ok():
        model_lookup = _model_list.ok_value
    else:
        model_lookup = {}

    largest = -1
    for val in model_lookup.values():
        largest = max(largest, val)

    for idx, model in enumerate(models):
        name = model['model']
        if name in model_lookup:
            model['ordering'] = model_lookup[name]
        else:
            model['ordering'] = model_lookup[name] = largest + 1
            largest += 1

    if (ret := await filesystem.write(flow_sheet, f"model_list", model_lookup)).is_err():
        return {"successful": False, "reason": ret.err_value}

    return {"models": sorted(models, key=lambda x: (x['ordering'], x['model']), reverse=True), 'successful': True}


@api_router.get("/thinking")
async def get_thinking(request: Request, model=None):
    flow_sheet = gen_flow_sheet(request.headers)

    if (_ret := await list_thinking(flow_sheet, model)).is_err():
        return {"error": _ret.err_value}
    return {"thinking": _ret.ok_value, 'successful': True}


@ws_router.websocket("/speech_to_text")
async def websocket_endpoint(websocket: WebSocket):
    flow_sheet = gen_flow_sheet()

    await websocket.accept()

    if SKIP.get('AUDIO_INPUT'):
        await websocket.send_json({"error": "Speech to text is disabled in settings."})
        await websocket.close()
        return

    try:
        async def read_audio():
            while True:
                yield await websocket.receive_bytes()

        # Setup teh audio to text
        if (ret := await media.audio.speech_to_text(
            flow_sheet,
            audio_stream=read_audio(),
        )).is_err():
            print("error", ret.err_value)
            return {"error": ret.err_value}

        async for msg in ret.ok_value:
            print(msg)
            await websocket.send_json(msg)

    except WebSocketDisconnect:
        print("WebSocket disconnected")
