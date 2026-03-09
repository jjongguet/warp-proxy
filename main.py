"""warp-proxy FastAPI 애플리케이션.

Oz CLI를 OpenAI-compatible API로 노출하는 엔트리포인트.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from config import Settings
from models import APIError, APIErrorEnvelope, ChatCompletionRequest
from oz_bridge import OzBridge, ProxyError


def create_app(*, settings: Settings | None = None, bridge: OzBridge | None = None) -> FastAPI:
    """FastAPI 앱을 생성한다. 테스트 시 settings/bridge를 주입할 수 있다."""
    resolved_settings = settings or Settings.from_env()
    resolved_bridge = bridge or OzBridge(resolved_settings)

    app = FastAPI(
        title="warp-proxy",
        version=resolved_settings.app_version,
        description="Warp Oz CLI → OpenAI-compatible API proxy",
        openapi_tags=[
            {"name": "Chat", "description": "OpenAI-compatible chat completions"},
            {"name": "Models", "description": "Model discovery"},
            {"name": "Admin", "description": "Operator endpoints"},
        ],
    )
    app.state.settings = resolved_settings
    app.state.bridge = resolved_bridge

    @app.exception_handler(ProxyError)
    async def proxy_error_handler(_: Request, exc: ProxyError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=APIErrorEnvelope(error=exc.error).model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        loc = first_error.get("loc", [])
        param = str(loc[-1]) if loc else None
        error_type = first_error.get("type", "validation_error")
        message = first_error.get("msg", "Invalid request.")
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

    return app


app = create_app()


if __name__ == "__main__":
    settings = Settings.from_env()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
