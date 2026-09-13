#!/usr/bin/env python3
"""warp-proxy 로컬 서버 실행 진입점.

사용 예:

    python run.py                          # 기본 127.0.0.1:29113 으로 기동
    WARP_PROXY_PORT=29200 python run.py    # 포트 변경

설정은 config.Settings.from_env() 환경 변수를 따른다 (README 참고).

호환성 기본값: 이 진입점은 WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS를
명시하지 않으면 true로 기동한다. OpenAI SDK, GJC 같은 클라이언트가
보내는 stream_options / max_completion_tokens 필드가 400으로 거부되지
않도록 하기 위해서다. 엄격 모드는 =false로 명시하면 된다.
"""
from __future__ import annotations

import os

import uvicorn

from config import Settings


def main() -> None:
    # 사람이 직접 띄우는 서버는 클라이언트 호환을 우선한다.
    os.environ.setdefault("WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS", "true")
    settings = Settings.from_env()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
