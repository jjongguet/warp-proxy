"""warp-proxy FastAPI 애플리케이션.

Oz CLI를 OpenAI-compatible + Anthropic-compatible API로 노출하는 엔트리포인트.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from config import Settings
from models import (
    APIError,
    APIErrorEnvelope,
    AnthropicContentBlockDeltaEvent,
    AnthropicContentBlockStartEvent,
    AnthropicContentBlockStopEvent,
    AnthropicCountTokensResponse,
    AnthropicError,
    AnthropicErrorEnvelope,
    AnthropicMessageDeltaEvent,
    AnthropicMessageResponse,
    AnthropicMessageStartEvent,
    AnthropicMessageStopEvent,
    AnthropicMessagesRequest,
    AnthropicStreamErrorEvent,
    AnthropicTextBlock,
    AnthropicTextDelta,
    AnthropicUsage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ResponsesRequest,
)
from oz_bridge import OzBridge, ProxyError


def _anthropic_error_from_proxy(exc: ProxyError) -> AnthropicErrorEnvelope:
    return AnthropicErrorEnvelope(error=AnthropicError(type=exc.error.type, message=exc.error.message))


def _anthropic_sse_event(event_name: str, payload_json: str) -> str:
    return f"event: {event_name}\ndata: {payload_json}\n\n"

def _estimate_token_count_from_text(text: str) -> int:
    normalized = text.strip()
    if not normalized:
        return 0
    return len(normalized.split())


def _anthropic_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _anthropic_content_to_text([content])
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
                continue
            if block_type == "tool_result":
                parts.append(_anthropic_content_to_text(block.get("content", "")))
                continue
            if block_type == "tool_use":
                name = str(block.get("name", "tool"))
                tool_input = block.get("input")
                rendered_input = json.dumps(tool_input, ensure_ascii=False) if tool_input is not None else ""
                parts.append(f"[tool_use:{name}] {rendered_input}".strip())
                continue
            parts.append(json.dumps(block, ensure_ascii=False))
            continue
        parts.append(str(block))
    return "\n".join(part for part in parts if part).strip()


def _anthropic_request_to_chat_request(request: AnthropicMessagesRequest) -> ChatCompletionRequest:
    mapped_messages: list[ChatMessage] = []
    system_text = _anthropic_content_to_text(request.system)
    if system_text:
        mapped_messages.append(ChatMessage(role="system", content=system_text))
    for message in request.messages:
        mapped_messages.append(ChatMessage(role=message.role, content=_anthropic_content_to_text(message.content)))
    if not mapped_messages:
        raise ProxyError(
            status_code=400,
            code="invalid_request",
            message="messages must contain at least one message.",
            param="messages",
        )
    return ChatCompletionRequest(
        model=request.model,
        messages=mapped_messages,
        stream=request.stream,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens,
        stop=request.stop_sequences,
        metadata=request.metadata,
    )


def _estimate_anthropic_input_tokens(
    bridge: OzBridge,
    request: AnthropicMessagesRequest,
    chat_request: ChatCompletionRequest,
) -> int:
    base = bridge.estimate_input_tokens(chat_request)
    extras: list[str] = []
    if request.tools is not None:
        extras.append(json.dumps(request.tools, ensure_ascii=False))
    if request.tool_choice is not None:
        extras.append(json.dumps(request.tool_choice, ensure_ascii=False))
    return base + _estimate_token_count_from_text("\n".join(extras))


def _chat_completion_to_anthropic(
    response: ChatCompletionResponse,
    *,
    input_tokens_estimate: int,
) -> AnthropicMessageResponse:
    content = ""
    if response.choices:
        content = response.choices[0].message.content
    output_tokens_estimate = _estimate_token_count_from_text(content)
    return AnthropicMessageResponse(
        id=response.id,
        model=response.model,
        content=[AnthropicTextBlock(text=content)],
        usage=AnthropicUsage(
            input_tokens=input_tokens_estimate,
            output_tokens=output_tokens_estimate,
        ),
    )


async def _stream_anthropic_messages(bridge: OzBridge, stream, *, model: str) -> AsyncIterator[str]:
    input_tokens_estimate = bridge.estimate_input_tokens(stream.prepared.request)
    output_tokens_estimate = 0
    message = AnthropicMessageResponse(
        id=stream.prepared.response_id,
        model=model,
        content=[],
        stop_reason=None,
        stop_sequence=None,
        usage=AnthropicUsage(input_tokens=input_tokens_estimate, output_tokens=0),
    )
    yield _anthropic_sse_event(
        "message_start",
        AnthropicMessageStartEvent(message=message).model_dump_json(exclude_none=True),
    )
    yield _anthropic_sse_event(
        "content_block_start",
        AnthropicContentBlockStartEvent(content_block=AnthropicTextBlock(text="")).model_dump_json(exclude_none=True),
    )
    try:
        async for delta in bridge.stream_chat_completion_text_deltas(stream):
            if not delta:
                continue
            output_tokens_estimate += _estimate_token_count_from_text(delta)
            yield _anthropic_sse_event(
                "content_block_delta",
                AnthropicContentBlockDeltaEvent(delta=AnthropicTextDelta(text=delta)).model_dump_json(exclude_none=True),
            )
    except ProxyError as exc:
        yield _anthropic_sse_event(
            "error",
            AnthropicStreamErrorEvent(error=AnthropicError(type=exc.error.type, message=exc.error.message)).model_dump_json(exclude_none=True),
        )
        return
    yield _anthropic_sse_event(
        "content_block_stop",
        AnthropicContentBlockStopEvent().model_dump_json(exclude_none=True),
    )
    yield _anthropic_sse_event(
        "message_delta",
        AnthropicMessageDeltaEvent(
            usage=AnthropicUsage(
                input_tokens=input_tokens_estimate,
                output_tokens=output_tokens_estimate,
            ),
        ).model_dump_json(exclude_none=True),
    )
    yield _anthropic_sse_event(
        "message_stop",
        AnthropicMessageStopEvent().model_dump_json(exclude_none=True),
    )


def _openai_responses_sse_event(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _response_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _response_content_to_text([content])
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type in {"input_text", "output_text", "text"} and isinstance(block.get("text"), str):
                parts.append(block["text"])
                continue
            if block_type == "function_call_output":
                parts.append(_response_content_to_text(block.get("output")))
                continue
            if block_type == "input_image":
                image_url = block.get("image_url")
                if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                    parts.append(f"[image:{image_url['url']}]")
                    continue
                if isinstance(image_url, str):
                    parts.append(f"[image:{image_url}]")
                    continue
            parts.append(json.dumps(block, ensure_ascii=False))
            continue
        parts.append(str(block))
    return "\n".join(part for part in parts if part).strip()


def _responses_input_to_messages(input_value: Any) -> list[ChatMessage]:
    if input_value is None:
        return []
    if isinstance(input_value, str):
        return [ChatMessage(role="user", content=input_value)]
    if isinstance(input_value, list):
        messages: list[ChatMessage] = []
        for item in input_value:
            messages.extend(_responses_input_to_messages(item))
        return messages
    if not isinstance(input_value, dict):
        return [ChatMessage(role="user", content=str(input_value))]
    item_type = input_value.get("type")
    if item_type == "message" or "role" in input_value:
        role = str(input_value.get("role", "user"))
        content = _response_content_to_text(input_value.get("content"))
        return [ChatMessage(role=role, content=content)]
    if item_type == "input_text" and isinstance(input_value.get("text"), str):
        return [ChatMessage(role="user", content=input_value["text"])]
    if item_type == "function_call_output":
        call_id = input_value.get("call_id")
        output = _response_content_to_text(input_value.get("output"))
        prefix = f"[function_call_output:{call_id}] " if call_id else ""
        return [ChatMessage(role="tool", content=f"{prefix}{output}".strip())]
    return [ChatMessage(role="user", content=_response_content_to_text(input_value))]


def _responses_request_to_chat_request(request: ResponsesRequest) -> ChatCompletionRequest:
    mapped_messages: list[ChatMessage] = []
    instructions_text = _response_content_to_text(request.instructions)
    if instructions_text:
        mapped_messages.append(ChatMessage(role="system", content=instructions_text))
    mapped_messages.extend(_responses_input_to_messages(request.input))
    if not mapped_messages:
        raise ProxyError(
            status_code=400,
            code="invalid_request",
            message="input must contain at least one message.",
            param="input",
        )
    metadata = dict(request.metadata or {})
    if request.previous_response_id and "warp_previous_response_id" not in metadata:
        metadata["warp_previous_response_id"] = request.previous_response_id
    return ChatCompletionRequest(
        model=request.model,
        messages=mapped_messages,
        stream=request.stream,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_output_tokens,
        stop=request.stop,
        user=request.user,
        metadata=metadata or None,
    )


def _responses_usage_payload(bridge: OzBridge, chat_request: ChatCompletionRequest, *, output_text: str) -> dict[str, Any]:
    input_tokens = bridge.estimate_input_tokens(chat_request)
    output_tokens = _estimate_token_count_from_text(output_text)
    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": output_tokens,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": input_tokens + output_tokens,
    }


def _response_defaults(request: ResponsesRequest) -> dict[str, Any]:
    return {
        "instructions": _response_content_to_text(request.instructions) or None,
        "max_output_tokens": request.max_output_tokens,
        "parallel_tool_calls": False,
        "previous_response_id": request.previous_response_id,
        "reasoning": None,
        "temperature": request.temperature if request.temperature is not None else 1.0,
        "text": {"format": {"type": "text"}},
        "tool_choice": request.tool_choice if request.tool_choice is not None else "auto",
        "tools": request.tools if request.tools is not None else [],
        "top_p": request.top_p if request.top_p is not None else 1.0,
        "truncation": request.truncation if request.truncation is not None else "disabled",
        "user": request.user,
        "metadata": request.metadata or {},
    }


def _chat_completion_to_response_object(
    bridge: OzBridge,
    response: ChatCompletionResponse,
    *,
    request: ResponsesRequest,
    chat_request: ChatCompletionRequest,
) -> dict[str, Any]:
    output_text = ""
    if response.choices:
        output_text = response.choices[0].message.content
    message_item = {
        "id": f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [
            {
                "type": "output_text",
                "text": output_text,
                "annotations": [],
            }
        ],
    }
    payload: dict[str, Any] = {
        "id": response.id,
        "object": "response",
        "created_at": response.created,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": response.model,
        "output": [message_item],
        "usage": _responses_usage_payload(bridge, chat_request, output_text=output_text),
        "output_text": output_text,
    }
    payload.update(_response_defaults(request))
    return payload


async def _stream_openai_responses(
    bridge: OzBridge,
    stream,
    *,
    request: ResponsesRequest,
    chat_request: ChatCompletionRequest,
) -> AsyncIterator[str]:
    response_id = stream.prepared.response_id
    created_at = stream.prepared.created
    model = stream.prepared.request.model
    message_id = f"msg_{uuid.uuid4().hex}"
    defaults = _response_defaults(request)
    created_payload = {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": "in_progress",
        "error": None,
        "incomplete_details": None,
        "model": model,
        "output": [],
        "usage": None,
        "output_text": "",
        **defaults,
    }
    yield _openai_responses_sse_event(
        "response.created",
        {"type": "response.created", "response": created_payload},
    )
    yield _openai_responses_sse_event(
        "response.in_progress",
        {"type": "response.in_progress", "response": created_payload},
    )
    yield _openai_responses_sse_event(
        "response.output_item.added",
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "id": message_id,
                "type": "message",
                "status": "in_progress",
                "role": "assistant",
                "content": [],
            },
        },
    )
    yield _openai_responses_sse_event(
        "response.content_part.added",
        {
            "type": "response.content_part.added",
            "output_index": 0,
            "content_index": 0,
            "item_id": message_id,
            "part": {"type": "output_text", "text": "", "annotations": []},
        },
    )

    chunks: list[str] = []
    try:
        async for delta in bridge.stream_chat_completion_text_deltas(stream):
            if not delta:
                continue
            chunks.append(delta)
            yield _openai_responses_sse_event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "content_index": 0,
                    "item_id": message_id,
                    "delta": delta,
                },
            )
    except ProxyError as exc:
        yield _openai_responses_sse_event(
            "error",
            {
                "type": "error",
                "code": exc.error.code,
                "message": exc.error.message,
                "param": exc.error.param,
            },
        )
        return

    output_text = "".join(chunks)
    completed_item = {
        "id": message_id,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": output_text, "annotations": []}],
    }
    yield _openai_responses_sse_event(
        "response.output_text.done",
        {
            "type": "response.output_text.done",
            "output_index": 0,
            "content_index": 0,
            "item_id": message_id,
            "text": output_text,
        },
    )
    yield _openai_responses_sse_event(
        "response.content_part.done",
        {
            "type": "response.content_part.done",
            "output_index": 0,
            "content_index": 0,
            "item_id": message_id,
            "part": {"type": "output_text", "text": output_text, "annotations": []},
        },
    )
    yield _openai_responses_sse_event(
        "response.output_item.done",
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": completed_item,
        },
    )
    completed_payload = {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": model,
        "output": [completed_item],
        "usage": _responses_usage_payload(bridge, chat_request, output_text=output_text),
        "output_text": output_text,
        **defaults,
    }
    yield _openai_responses_sse_event(
        "response.completed",
        {"type": "response.completed", "response": completed_payload},
    )
    yield "event: done\ndata: [DONE]\n\n"


def create_app(*, settings: Settings | None = None, bridge: OzBridge | None = None) -> FastAPI:
    """FastAPI 앱을 생성한다. 테스트 시 settings/bridge를 주입할 수 있다."""
    resolved_settings = settings or Settings.from_env()
    resolved_bridge = bridge or OzBridge(resolved_settings)

    app = FastAPI(
        title="warp-proxy",
        version=resolved_settings.app_version,
        description="Warp Oz CLI → OpenAI-compatible and Anthropic-compatible API proxy",
        openapi_tags=[
            {"name": "Chat", "description": "OpenAI-compatible chat completions and responses"},
            {"name": "Anthropic", "description": "Anthropic-compatible messages API"},
            {"name": "Models", "description": "Model discovery"},
            {"name": "Admin", "description": "Operator endpoints"},
        ],
    )
    app.state.settings = resolved_settings
    app.state.bridge = resolved_bridge

    @app.exception_handler(ProxyError)
    async def proxy_error_handler(request: Request, exc: ProxyError) -> JSONResponse:
        if request.url.path.startswith("/v1/messages"):
            return JSONResponse(status_code=exc.status_code, content=_anthropic_error_from_proxy(exc).model_dump())
        return JSONResponse(status_code=exc.status_code, content=APIErrorEnvelope(error=exc.error).model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        loc = first_error.get("loc", [])
        param = str(loc[-1]) if loc else None
        error_type = first_error.get("type", "validation_error")
        message = first_error.get("msg", "Invalid request.")
        if request.url.path.startswith("/v1/messages"):
            return JSONResponse(
                status_code=400,
                content=AnthropicErrorEnvelope(error=AnthropicError(message=message)).model_dump(),
            )
        if error_type == "extra_forbidden":
            code = "unsupported_field"
        elif param == "messages":
            code = "invalid_message_content"
        else:
            code = "invalid_request"
        return JSONResponse(
            status_code=400,
            content=APIErrorEnvelope(error=APIError(message=message, code=code, param=param)).model_dump(),
        )

    @app.get("/v1/models", summary="List models", tags=["Models"])
    async def list_models() -> dict:
        return (await resolved_bridge.list_models()).model_dump()

    @app.get("/admin/status", summary="Service status", tags=["Admin"])
    async def admin_status() -> dict:
        return (await resolved_bridge.get_admin_status()).model_dump()

    @app.post("/v1/chat/completions", summary="Create chat completion", tags=["Chat"])
    async def create_chat_completions(request: ChatCompletionRequest):
        if request.stream:
            stream = await resolved_bridge.prepare_stream_chat_completion(request)
            return StreamingResponse(
                resolved_bridge.stream_chat_completion_sse(stream),
                media_type="text/event-stream",
            )
        return (await resolved_bridge.create_chat_completion(request)).model_dump()

    @app.post("/v1/responses", summary="Create response", tags=["Chat"])
    async def create_responses(request: ResponsesRequest):
        chat_request = _responses_request_to_chat_request(request)
        if request.stream:
            stream = await resolved_bridge.prepare_stream_chat_completion(chat_request)
            return StreamingResponse(
                _stream_openai_responses(
                    resolved_bridge,
                    stream,
                    request=request,
                    chat_request=chat_request,
                ),
                media_type="text/event-stream",
            )
        response = await resolved_bridge.create_chat_completion(chat_request)
        return _chat_completion_to_response_object(
            resolved_bridge,
            response,
            request=request,
            chat_request=chat_request,
        )

    @app.post("/v1/messages", summary="Create message", tags=["Anthropic"])
    async def create_anthropic_message(request: AnthropicMessagesRequest):
        chat_request = _anthropic_request_to_chat_request(request)
        if request.stream:
            stream = await resolved_bridge.prepare_stream_chat_completion(chat_request)
            return StreamingResponse(
                _stream_anthropic_messages(resolved_bridge, stream, model=chat_request.model),
                media_type="text/event-stream",
            )
        input_tokens_estimate = _estimate_anthropic_input_tokens(resolved_bridge, request, chat_request)
        response = await resolved_bridge.create_chat_completion(chat_request)
        return _chat_completion_to_anthropic(
            response,
            input_tokens_estimate=input_tokens_estimate,
        ).model_dump(exclude_none=True)

    @app.post("/v1/messages/count_tokens", summary="Count message tokens", tags=["Anthropic"])
    async def count_anthropic_message_tokens(request: AnthropicMessagesRequest):
        chat_request = _anthropic_request_to_chat_request(request)
        estimated_tokens = _estimate_anthropic_input_tokens(resolved_bridge, request, chat_request)
        return AnthropicCountTokensResponse(input_tokens=estimated_tokens).model_dump()

    return app


app = create_app()


if __name__ == "__main__":
    settings = Settings.from_env()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
