#!/usr/bin/env python3
"""warp-proxy 로컬 서버 실행 진입점.

사용 예:

    pip install -r requirements.txt    # venv 안에서 (아래 참고)
    python run.py                      # 기본 127.0.0.1:29113 으로 기동
    WARP_PROXY_PORT=29200 python run.py

실행 환경 자동 복구: macOS Homebrew/Xcode Python은 pip 설치를 거부하거나
(PEP 668) 버전이 낮아서 곧바로 실행이 안 될 수 있다. run.py는 의존성
임포트에 실패하면 레포의 .venv 로 재진입한다(.venv 가 없으면 3.11+
인터프리터로 생성 후 requirements.txt 를 설치). 어떤 python 으로 실행해도
결국 동작하는 것이 목적이다.

설정은 config.Settings.from_env() 환경 변수를 따른다 (README 참고).

호환성 기본값: 이 진입점은 WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS를
명시하지 않으면 true로 기동한다. OpenAI SDK, GJC 같은 클라이언트가
보내는 stream_options / max_completion_tokens 필드가 400으로 거부되지
않도록 하기 위해서다. 엄격 모드는 =false로 명시하면 된다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SRC = ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_BOOTSTRAP_FLAG = "WARP_PROXY_RUN_BOOTSTRAPPED"
_MISSING_DEPS_MESSAGE = """\
[warp-proxy] 의존성(fastapi/pydantic/uvicorn)을 찾지 못했다.

  python3.11+ 로 가상환경을 만들고 설치한 뒤 실행하라:

      python3 -m venv .venv
      source .venv/bin/activate
      pip install -r requirements.txt
      python run.py
"""


def _deps_available() -> bool:
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        return False
    return True


def _reexec_into_venv() -> None:
    venv_python = ROOT / ".venv" / "bin" / "python"
    requirements = ROOT / "requirements.txt"
    if not venv_python.exists():
        if sys.version_info < (3, 11):
            raise SystemExit(_MISSING_DEPS_MESSAGE)
        subprocess.run(
            [sys.executable, "-m", "venv", str(ROOT / ".venv")],
            check=True,
            cwd=str(ROOT),
        )
    try:
        # uv 등 pip 없이 만든 venv 도 지원한다.
        subprocess.run(
            [str(venv_python), "-m", "ensurepip", "--upgrade"],
            check=True,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", str(requirements)],
            check=True,
            cwd=str(ROOT),
        )
        # uv venv 에는 pip 스크립트가 없을 수 있다. 활성화 후
        # `pip install -r requirements.txt` 가 그대로 동작하도록 보강한다.
        pip_shim = venv_python.parent / "pip"
        if not pip_shim.exists() and (venv_python.parent / "pip3").exists():
            with suppress(OSError):
                pip_shim.symlink_to("pip3")
    except subprocess.CalledProcessError:
        raise SystemExit(_MISSING_DEPS_MESSAGE) from None
    os.environ[_BOOTSTRAP_FLAG] = "1"
    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve())])


def main() -> None:
    if not _deps_available():
        if os.environ.get(_BOOTSTRAP_FLAG) == "1":
            raise SystemExit(_MISSING_DEPS_MESSAGE)
        _reexec_into_venv()
        return  # exec 성공 시 도달하지 않는다

    import uvicorn

    from warp_proxy.config import Settings
    from warp_proxy.main import create_app

    # 사람이 직접 띄우는 서버는 클라이언트 호환을 우선한다.
    os.environ.setdefault("WARP_PROXY_IGNORE_UNSUPPORTED_FIELDS", "true")
    settings = Settings.from_env()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
