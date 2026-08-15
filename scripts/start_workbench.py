#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def build_launcher_env(repo: Path, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env["OPENAI_BASE_URL"] = "https://api.deepseek.com"
    env["CHAT_MODEL"] = "deepseek-v4-flash"
    env["SMALL_MODEL"] = "deepseek-v4-flash"
    env.setdefault(
        "PAPER_RAG_DSH_CREDENTIALS_PATH",
        str(repo / "data/runtime/deepseek-harness/credentials/.credentials.yaml"),
    )
    return env


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    env = build_launcher_env(repo)
    api = subprocess.Popen(
        [sys.executable, "-m", "paper_rag.workbench", "--host", "127.0.0.1", "--port", "3091"],
        cwd=repo,
        env={**env, "PYTHONPATH": str(repo / "src")},
    )
    ui = subprocess.Popen(
        ["pnpm", "--dir", "integrations/paper-rag-workbench", "dev"],
        cwd=repo,
        env=env,
    )
    print("paper rag workbench: http://127.0.0.1:3090", flush=True)
    try:
        return ui.wait()
    finally:
        for proc in (ui, api):
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)


if __name__ == "__main__":
    raise SystemExit(main())
