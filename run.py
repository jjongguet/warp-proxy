#!/usr/bin/env python3
"""warp-proxy 로컬 서버 실행 진입점.

사용 예:

    python run.py                          # 기본 127.0.0.1:29113 으로 기동
    WARP_PROXY_PORT=29200 python run.py    # 포트 변경

설정은 config.Settings.from_env() 환경 변수를 따른다 (README 참고).
"""
from __future__ import annotations

import uvicorn

from config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
