#!/usr/bin/env python3
"""claude-pipe: Send prompts to an AI CLI agent running in a tmux session, capture response."""

import os
import re
import sys
import time
from importlib.metadata import version
from typing import List

import libtmux

# --- Constants ---
SESSION_NAME = "claude-pipe"
AGENT_CMD = "claude"
AGENT_PROCESS_NAMES = ("node", "claude")
PROMPT_CHAR = "❯"  # ❯
PROMPT_VISIBLE_LINES = 8
END_MARKER = "===PIPE_END==="
END_MARKER_INSTRUCTION = f" (When done, print {END_MARKER} on its own line)"

SUBMIT_DELAY_S = 0.6
POLL_INTERVAL_S = 0.5
IDLE_TIMEOUT_S = 5.0
AGENT_STARTUP_WAIT_S = 5.0
CLEAR_SCREEN_WAIT_S = 1.0
MAX_WAIT_S = 300


class ClaudePipe:
    """A class to manage sending prompts to a Claude CLI agent in a tmux session."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.server = libtmux.Server()
        self.session = self._get_or_create_session()
        self.pane = self.session.windows[0].panes[0]

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[claude-pipe] {msg}", file=sys.stderr)

    @staticmethod
    def _err(msg: str) -> None:
        print(f"[claude-pipe] ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    def _get_or_create_session(self) -> libtmux.Session:
        try:
            for s in self.server.sessions:
                if s.name == SESSION_NAME:
                    return s
        except Exception:
            pass  # no tmux server running yet
        return self.server.new_session(session_name=SESSION_NAME)

    @staticmethod
    def _capture_pane(pane: libtmux.Pane, scrollback: int = 0) -> str:
        """Capture pane text. scrollback=N includes N lines of history."""
        args = ["-p"]
        if scrollback:
            args += ["-S", str(-scrollback)]
        result = pane.cmd("capture-pane", *args)
        return "\n".join(result.stdout)

    @staticmethod
    def _send_and_enter(pane: libtmux.Pane, text: str) -> None:
        """Type *text* literally, wait, then press Enter."""
        pane.send_keys(text, enter=False, literal=True)
        time.sleep(SUBMIT_DELAY_S)
        pane.cmd("send-keys", "Enter")

    @staticmethod
    def _pane_current_command(pane: libtmux.Pane) -> str:
        result = pane.cmd("display-message", "-p", "#{pane_current_command}")
        return (result.stdout[0] if result.stdout else "").lower()

    def _is_agent_running(self) -> bool:
        cmd = self._pane_current_command(self.pane)
        return any(name in cmd for name in AGENT_PROCESS_NAMES)

    def _prompt_visible(self) -> bool:
        """True when the Claude Code ❯ prompt is visible."""
        lines = self._capture_pane(self.pane).split("\n")
        for line in lines[-PROMPT_VISIBLE_LINES:]:
            stripped = line.strip()
            if stripped.startswith(PROMPT_CHAR) and len(stripped) <= 2:
                return True
        return False

    def _wait_for_prompt(self, timeout: float = 60) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._prompt_visible():
                return True
            time.sleep(POLL_INTERVAL_S)
        return False

    @staticmethod
    def _count_standalone_markers(text: str) -> int:
        return sum(1 for line in text.split("\n") if line.strip() == END_MARKER)

    def _wait_for_response(self, baseline: str) -> str:
        baseline_marker_count = self._count_standalone_markers(baseline)
        time.sleep(3.0)
        last_content = ""
        last_change_t = time.time()
        start = time.time()

        while time.time() - start < MAX_WAIT_S:
            content = self._capture_pane(self.pane, scrollback=10000)
            if self._count_standalone_markers(content) > baseline_marker_count:
                time.sleep(1.0)
                return self._capture_pane(self.pane, scrollback=10000)

            if content != last_content:
                last_content = content
                last_change_t = time.time()

            idle = time.time() - last_change_t
            if (idle >= IDLE_TIMEOUT_S and self._prompt_visible()) or \
               (idle >= IDLE_TIMEOUT_S * 3):
                return content

            time.sleep(POLL_INTERVAL_S)

        self._err("timed out waiting for response")
        return self._capture_pane(self.pane, scrollback=10000)

    @staticmethod
    def _extract_response(output: str, sent_message: str) -> str:
        lines = output.split("\n")
        needle = sent_message[:60]
        start_idx = -1
        for i, line in enumerate(lines):
            if needle in line:
                start_idx = i
                break

        if start_idx == -1:
            return output.strip()

        tail = lines[start_idx + 1:]
        cleaned: List[str] = []
        response_started = False
        for line in tail:
            stripped = line.strip()
            if stripped == END_MARKER:
                break
            if END_MARKER in stripped:
                line = line.replace(END_MARKER, "").rstrip()
                stripped = line.strip()
                if not stripped:
                    break
            if not response_started:
                if stripped.startswith(("●", "⏿", "⎇")) or \
                   (stripped and not stripped.endswith(")")):
                    response_started = True
                else:
                    continue
            cleaned.append(line)

        noise = {"", PROMPT_CHAR, f"{PROMPT_CHAR} ", "? for", "shortcuts", "? for shortcuts"}
        while cleaned and (cleaned[-1].strip() in noise or set(cleaned[-1].strip()) <= {"\u2500", " "}):
            cleaned.pop()

        return "\n".join(cleaned)

    @staticmethod
    def _strip_bullets(text: str) -> str:
        lines = text.split("\n")
        out: List[str] = []
        for line in lines:
            line = re.sub(r"^(\s*)[●⎿]\s?", r"\1", line)
            if out and line.startswith("  ") and not line.startswith("    "):
                line = line[2:]
            out.append(line)
        return "\n".join(out)

    def run(self, message: str) -> str:
        """Run the full process of sending a message and getting a response."""
        self._log("connecting to tmux…")

        if not self._is_agent_running():
            self._log(f"starting {AGENT_CMD}…")
            self._send_and_enter(self.pane, AGENT_CMD)
            time.sleep(AGENT_STARTUP_WAIT_S)
            if not self._wait_for_prompt(timeout=30):
                self._err("prompt not detected after starting agent")

        self._log("/clear")
        self._send_and_enter(self.pane, "/clear")
        time.sleep(CLEAR_SCREEN_WAIT_S)
        self._wait_for_prompt(timeout=10)

        baseline = self._capture_pane(self.pane, scrollback=10000)
        prompt = message + END_MARKER_INSTRUCTION
        self._log("sending prompt…")
        self._send_and_enter(self.pane, prompt)

        self._log("waiting for response…")
        output = self._wait_for_response(baseline)

        return self._strip_bullets(self._extract_response(output, message))

def main():
    """Main entry point of the script."""
    args = [a for a in sys.argv[1:] if a != "-v"]
    verbose = "-v" in sys.argv[1:]

    if any(arg in args for arg in ["help", "--help", "-h", "--version"]):
        print(version("claude-pipe"))
        sys.exit(0)

    if args:
        message = " ".join(args)
    elif not sys.stdin.isatty():
        message = sys.stdin.read().strip()
    else:
        script_name = os.path.basename(sys.argv[0])
        print(f"Usage:", file=sys.stderr)
        print(f"  {script_name} [-v] <message>", file=sys.stderr)
        print(f"  <some-command> | {script_name} [-v]", file=sys.stderr)
        sys.exit(1)

    if not message:
        ClaudePipe._err("empty message")

    try:
        pipe = ClaudePipe(verbose=verbose)
        response = pipe.run(message)
        print(response)
    except Exception as e:
        ClaudePipe._err(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()