from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


class OpenCodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenCodeResult:
    output: str
    returncode: int
    session_id: Optional[str] = None


class OpenCodeClient:
    def __init__(
        self,
        binary: str,
        workdir: Path,
        timeout_seconds: float,
        agent: Optional[str] = None,
        attach_url: Optional[str] = None,
        skip_permissions: bool = False,
        reply_full_output: bool = False,
    ) -> None:
        self._binary = binary
        self._workdir = workdir
        self._timeout_seconds = timeout_seconds
        self._agent = agent
        self._attach_url = attach_url
        self._skip_permissions = skip_permissions
        self._reply_full_output = reply_full_output

    def check_ready(self) -> str:
        path = shutil.which(self._binary)
        if path is None:
            raise OpenCodeError(f"OpenCode executable not found: {self._binary}")
        return path

    def run(
        self,
        prompt: str,
        model: Optional[str],
        title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> OpenCodeResult:
        self.check_ready()
        args: List[str] = [self._binary, "run"]
        if session_id:
            args.extend(["--session", session_id])
        if model:
            args.extend(["--model", model])
        if self._agent:
            args.extend(["--agent", self._agent])
        if self._attach_url:
            args.extend(["--attach", self._attach_url])
        if self._skip_permissions:
            args.append("--dangerously-skip-permissions")
        if title:
            args.extend(["--title", title[:80]])
        args.extend(["--format", "json"])
        args.append(prompt)

        try:
            completed = subprocess.run(
                args,
                cwd=self._workdir,
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OpenCodeError(f"OpenCode timed out after {self._timeout_seconds:.0f}s") from exc

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        output, parsed_session_id = self._parse_run_output(stdout)
        if not output:
            output = stderr
        if completed.returncode != 0:
            detail = output or f"exit code {completed.returncode}"
            raise OpenCodeError(f"OpenCode failed: {detail}")
        if not output:
            raise OpenCodeError("OpenCode finished without output")
        return OpenCodeResult(output=output, returncode=completed.returncode, session_id=parsed_session_id or session_id)

    def _parse_run_output(self, stdout: str) -> tuple[str, Optional[str]]:
        if not stdout:
            return "", None

        texts: List[str] = []
        session_id: Optional[str] = None
        parsed_any = False
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            parsed_any = True
            if isinstance(event.get("sessionID"), str):
                session_id = event["sessionID"]
            part = event.get("part")
            if isinstance(part, dict):
                if isinstance(part.get("sessionID"), str):
                    session_id = part["sessionID"]
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])

        if parsed_any:
            output = "".join(texts) if self._reply_full_output else _last_text_part(texts)
            return output.strip(), session_id
        return stdout.strip(), None

    def list_models(self, provider: Optional[str] = None, refresh: bool = False) -> str:
        self.check_ready()
        args: List[str] = [self._binary, "models"]
        if refresh:
            args.append("--refresh")
        if provider:
            args.append(provider)
        completed = subprocess.run(
            args,
            cwd=self._workdir,
            text=True,
            capture_output=True,
            timeout=min(self._timeout_seconds, 120),
            check=False,
        )
        output = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode != 0:
            raise OpenCodeError(output or f"opencode models failed with exit code {completed.returncode}")
        return output or "(OpenCode 没有返回模型列表)"


def _last_text_part(texts: List[str]) -> str:
    for text in reversed(texts):
        if text.strip():
            return text
    return ""
