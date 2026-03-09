"""OpenAI-compatible API 요청/응답 모델 정의.

Pydantic v2 BaseModel을 사용하며, FastAPI의 ReDoc/Swagger에 자동 반영된다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# 에러 모델
# ---------------------------------------------------------------------------


class APIErrorEnvelope(BaseModel):
    """에러 응답 외부 envelope. {"error": {...}} 형식."""
    error: "APIError"


class APIError(BaseModel):
    """OpenAI-style 에러 본문."""

    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str


# ---------------------------------------------------------------------------
# 요청 모델
# ---------------------------------------------------------------------------


class MessageTextPart(BaseModel):
    """메시지 content 배열의 텍스트 파트."""
    type: Literal["text"]
    text: str


class ChatMessage(BaseModel):
    """단일 대화 메시지. content는 문자열 또는 text 파트 배열."""

    role: str
    content: str | list[MessageTextPart]

    @model_validator(mode="before")
    @classmethod
    def validate_content(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise TypeError("message must be an object")
        content = data.get("content")
        if isinstance(content, str):
            return data
        if isinstance(content, list):
            for index, part in enumerate(content):
                if not isinstance(part, dict):
                    raise ValueError(f"messages content part at index {index} must be an object")
                if part.get("type") != "text" or not isinstance(part.get("text"), str):
                    raise ValueError(f"messages content part at index {index} must be a text part")
            return data
        raise ValueError("messages content must be a string or an array of text parts")

    def flattened_content(self) -> str:
        """content가 배열이면 \n으로 이어붙여 단일 문자열로 반환."""
        if isinstance(self.content, str):
            return self.content
        return "\n".join(part.text for part in self.content)


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(description="Model ID (e.g. `warp-oz-cli`)")
    messages: list[ChatMessage] = Field(description="Conversation messages")
    stream: bool = Field(False, description="Enable SSE streaming")
    temperature: float | None = Field(None, description="Sampling temperature")
    top_p: float | None = Field(None, description="Nucleus sampling")
    max_tokens: int | None = Field(None, description="Max response tokens")
    stop: str | list[str] | None = Field(None, description="Stop sequence(s)")
    user: str | None = Field(None, description="End-user identifier")
    metadata: dict[str, Any] | None = Field(
        None, description="Proxy metadata (e.g. `warp_previous_response_id` for continuation)",
    )

    # Accepted for OpenAI client compatibility — not forwarded to Oz.
    tools: Any | None = Field(None, description="Ignored — compatibility only")
    tool_choice: Any | None = Field(None, description="Ignored — compatibility only")
    functions: Any | None = Field(None, description="Ignored — compatibility only")
    function_call: Any | None = Field(None, description="Ignored — compatibility only")
    response_format: Any | None = Field(None, description="Ignored — compatibility only")
    audio: Any | None = Field(None, description="Ignored — compatibility only")
    parallel_tool_calls: Any | None = Field(None, description="Ignored — compatibility only")


# ---------------------------------------------------------------------------
# 응답 모델 (non-streaming)
# ---------------------------------------------------------------------------


class ChatCompletionMessage(BaseModel):
    """응답 메시지 본문."""

    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    """응답 선택지. warp-proxy는 항상 단일 choice(index=0)만 반환."""
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: Literal["stop"] = "stop"


class Usage(BaseModel):
    """Oz CLI는 토큰 정보를 반환하지 않으므로 항상 0."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """Non-streaming chat completion response."""

    id: str = Field(description="Unique response ID")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(description="Unix timestamp")
    model: str = Field(description="Model used")
    choices: list[ChatCompletionChoice] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


# ---------------------------------------------------------------------------
# 응답 모델 (streaming / SSE)
# ---------------------------------------------------------------------------


class ChatCompletionChunkDelta(BaseModel):
    """SSE chunk의 delta 페이로드."""

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    """SSE chunk 선택지."""

    index: int = 0
    delta: ChatCompletionChunkDelta = Field(default_factory=ChatCompletionChunkDelta)
    finish_reason: Literal["stop"] | None = None


class ChatCompletionChunkResponse(BaseModel):
    """SSE 스트리밍 응답 chunk."""
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice] = Field(default_factory=list)


class ModelDescriptor(BaseModel):
    id: str = Field(description="Model ID")
    object: Literal["model"] = "model"
    owned_by: str = "warp-proxy"


class ModelsResponse(BaseModel):
    """/v1/models 응답."""

    object: Literal["list"] = "list"
    data: list[ModelDescriptor]


# ---------------------------------------------------------------------------
# 운영 모델 (/admin/status)
# ---------------------------------------------------------------------------


class ModelAvailability(BaseModel):
    """모델 alias의 가용성 상태."""

    id: str
    available: bool
    reason: str | None = None


class CwdStatus(BaseModel):
    """작업 디렉토리 설정 상태."""
    configured: bool
    value: str | None = None


class VersionProbeStatus(BaseModel):
    """Warp CLI 버전 프로브 결과."""

    checked: bool
    supported: bool | None = None
    detected_version: str | None = None
    allow_unverified_warp_cli: bool
    verified_warp_versions: list[str]
    error_code: str | None = None
    error_message: str | None = None


class AdminStatusResponse(BaseModel):
    """Operator health-check response."""

    service: Literal["warp-proxy"] = "warp-proxy"
    version: str = Field(description="warp-proxy version")
    auth_mode: Literal["session", "api_key"] = Field(description="Current auth mode")
    cwd: CwdStatus = Field(description="Working directory status")
    models: list[ModelAvailability] = Field(description="Model availability")
    version_probe: VersionProbeStatus = Field(description="Warp CLI version check")


APIErrorEnvelope.model_rebuild()
