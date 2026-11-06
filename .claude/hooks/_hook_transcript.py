"""Shared transcript reader for Stop hooks that judge the assistant's final message.

Extracted 2026-08-06 when a second hook (`verify_judge_guard`) needed the same reader that
`architect_no_defer_guard` already had. Two copies of a JSONL parser is how they drift.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

#: HOOK-SPEED (2026-11-05): what a guard collects over the WHOLE session (every item a TodoWrite listed, every owner
#: message, every task written) only grows; it is kept per transcript beside the byte offset already read
#: (session_texts), so a call parses only what was written since -- the whole file once a session, never once a call.
INDEX_DIR = Path(tempfile.gettempdir()) / "claude-hook-session-index"

#: Backward-scan chunk. Transcripts reach tens of MB; the question is almost always about the last
#: few minutes, so the file is read from the END and the scan stops at the first older entry.
_REVERSE_CHUNK_BYTES = 256 * 1024


def _epoch(iso: object) -> float | None:
    """`2026-09-23T19:53:08.712Z` -> epoch seconds, or None for anything unparseable."""
    if not isinstance(iso, str) or not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _reset_verdict(raw: bytes, since: float) -> bool | None:
    """True: a compaction at/after `since`. False: an entry older than `since` (stop). None: go on."""
    if not raw.strip():
        return None
    try:
        record = json.loads(raw)
    except ValueError:
        return None
    stamp = _epoch(record.get("timestamp")) if isinstance(record, dict) else None
    if stamp is None:
        return None
    if stamp < since:
        return False
    if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
        return True
    return None


def _lines_backward(fh: BinaryIO) -> Iterator[bytes]:
    """The lines of a file opened "rb", LAST first, read in chunks from the end -- a question about the last few
    minutes costs a few KB however long the transcript is (765 MB measured 2026-10-21)."""
    fh.seek(0, os.SEEK_END)
    position = fh.tell()
    carry = b""
    while position > 0:
        step = min(_REVERSE_CHUNK_BYTES, position)
        position -= step
        fh.seek(position)
        lines = (fh.read(step) + carry).split(b"\n")
        carry = lines[0]  # possibly a partial line; completed by the next (earlier) chunk
        yield from reversed(lines[1:])
    yield carry


def records_backward(transcript_path: str) -> Iterator[dict[str, Any]]:
    """The transcript's records, LAST first, read from the end (_lines_backward); unparseable lines skipped, an
    unreadable file yields nothing. HOOK-SPEED (2026-11-05, owner: "now to edit or read or whatever, you take at least 1
    min"): five readers below loaded the WHOLE file into a list before reading its last few records -- a 1.43 GB
    transcript cost owner_first_guard 1.65 s per call (0.07 s on a 1.9 MB slice of the same session), on every call of
    every hook built on them. A turn is read from the end and the scan stops at its first record."""
    try:
        with open(transcript_path, "rb") as fh:
            for raw in _lines_backward(fh):
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except OSError:
        return


def session_texts(transcript_path: str, name: str, tags: tuple[bytes, ...], extract: Callable[[dict[str, Any]], list[str]], *,
                  unique: bool = False) -> list[str]:  # fmt: skip
    """Every text ``extract`` reads from the session's records whose line holds one of ``tags``, oldest first (``unique``:
    each once): the index's (``name`` + the transcript), then those in the lines written since its offset -- whole lines
    only, a line still being written is read next time; a file shorter than the offset was rewritten and is read again.
    Raises OSError on an unreadable transcript (the caller's fail-open)."""
    path = Path(transcript_path)
    index = INDEX_DIR / f"{hashlib.sha1(f'{name}|{transcript_path}'.encode()).hexdigest()}.json"
    try:
        saved = json.loads(index.read_text(encoding="utf-8"))
        offset, texts = int(saved["offset"]), [str(t) for t in saved["texts"]]
    except (OSError, ValueError, KeyError, TypeError):
        offset, texts = 0, []
    if path.stat().st_size < offset:
        offset, texts = 0, []
    known = set(texts) if unique else set()
    with path.open("rb") as fh:
        fh.seek(offset)
        for raw in fh:
            if not raw.endswith(b"\n"):
                break
            offset += len(raw)
            if not any(tag in raw for tag in tags):
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            for text in extract(rec) if isinstance(rec, dict) else []:
                if unique and text in known:
                    continue
                known.add(text)
                texts.append(text)
    try:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({"offset": offset, "texts": texts}), encoding="utf-8")
    except OSError:
        pass  # an unwritable index costs the next call a fuller read, never a wrong answer
    return texts


def context_reset_since(transcript_path: str, since: float) -> bool:
    """True when the transcript records a compaction at or after `since` (epoch seconds).

    HOOKRT-1, 2026-09-23: "I read that document" is true exactly until the context is reset.
    A flat time window got it wrong both ways -- it expired a doc still in the window every 30
    minutes (23 denials in one session) and would have kept one that a compaction had dropped.
    Reads BACKWARDS and stops at the first entry older than `since`, so a recent read costs a
    few KB however long the transcript is. Unreadable -> False (the caller decides its fallback).
    """
    try:
        with open(transcript_path, "rb") as fh:
            for raw in _lines_backward(fh):
                verdict = _reset_verdict(raw, since)
                if verdict is not None:
                    return verdict
            return False
    except OSError:
        return False


def last_user_text(transcript_path: str) -> str:
    """Text of the LAST user message — what the owner actually just told me to do.

    Added 2026-08-08 for `instruction_compliance_guard`: judging whether an instruction was obeyed
    requires reading the INSTRUCTION, not only my reply. Same fail-silent contract as below.
    """
    for rec in records_backward(transcript_path):
        if rec.get("type") != "user" and rec.get("role") != "user":
            continue
        msg = rec.get("message", rec)
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        return ""
    return ""


#: How far into a transcript the first user record may sit: before it come only bookkeeping records (queue
#: operations, snapshots), a handful at most. A file with none in this many lines is not a conversation.
_FIRST_USER_SCAN_LINES = 64


def first_user_text(transcript_path: str) -> str:
    """Text of the FIRST user message -- what opened the session; "" when unreadable or absent.

    Added 2026-10-12 for `_hook_mode.harness_side_session`: a side session the IDE opens to summarize a conversation
    is known by its opening prompt. Reads forward and stops at the first user record, so a 100 MB transcript costs
    a few lines.
    """
    try:
        with open(transcript_path, encoding="utf-8") as fh:
            for count, ln in enumerate(fh):
                if count >= _FIRST_USER_SCAN_LINES:
                    return ""
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(rec, dict) and (rec.get("type") == "user" or rec.get("role") == "user"):
                    msg = rec.get("message", rec)
                    return _block_text(msg) if isinstance(msg, dict) else ""
    except Exception:
        return ""
    return ""


def _block_text(msg: dict[str, Any]) -> str:
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def turn_assistant_texts(transcript_path: str) -> list[str]:
    """EVERY assistant message since the last user turn, oldest first.

    MEASURED HOLE (2026-08-09). Stop guards judged `last_assistant_text` — ONE message — while
    a working turn here routinely produces forty, and the behaviour they exist to catch lands
    mid-turn. Calibrating the detectors against 2,274 real assistant messages from six
    conversations found 58 matching `disowns_without_fixing` and 30 matching
    `cites_without_judging`: the patterns were live the whole time and the guards were still
    blind, because a violation in message 12 of 40 is not the message they read.

    Scanning the turn upgrades every guard at once and needs no new patterns — which is the
    difference between a detector and a denylist of incidents already survived.

    Fails silent (empty list) on any problem, same contract as the rest of this module.
    """
    texts: list[str] = []
    for rec in records_backward(transcript_path):
        if rec.get("type") == "user" or rec.get("role") == "user":
            # A tool RESULT is delivered as a user-role record; only a REAL user message ends the
            # turn. Without this the scan stops at the first tool result, so "every assistant
            # message since the last user turn" collapses to "the messages after the last tool
            # call" — in a turn with forty tool calls, that is the final message and nothing else.
            #
            # MEASURED 2026-08-15: `parallel_dev_audit_guard` was switched from
            # `last_assistant_text` to `turn_text` precisely to see a mid-turn statement, and it
            # STILL could not: `AUDITED 60765cd55` was written, work continued, and the state file
            # recorded 28 other SHAs and not that one, three stops running.
            #
            # `turn_tool_uses` below already carried this exact guard, with this exact comment.
            # The fix existed in this file, applied to one function and not its sibling — which
            # means the 2026-08-09 upgrade that moved several Stop guards onto `turn_text` has
            # been largely INERT since the day it shipped.
            content = rec.get("message", rec).get("content", "")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            break
        if rec.get("type") != "assistant" and rec.get("role") != "assistant":
            continue
        text = _block_text(rec.get("message", rec))
        if text:
            texts.append(text)
    return list(reversed(texts))


def turn_text(transcript_path: str) -> str:
    """The whole turn's assistant prose as one string, for predicates that take text."""
    return "\n\n".join(turn_assistant_texts(transcript_path))


def turn_prose(transcript_path: str, *, since_tool_result: bool = False) -> str:
    """The turn's prose from ``text`` AND ``thinking`` blocks, oldest first, as one string.

    MEASURED 2026-09-17: a PreToolUse guard reading only ``text`` blocks denied an edit whose facts
    were stated two messages earlier. In five of the seven preceding messages the visible prose was
    never stored as a ``text`` block at all -- the transcript held an empty (redacted) thinking
    record plus a thinking SUMMARY of what was said. ``turn_text`` is right for Stop guards judging
    the final reply; a guard asking "was X said before this call" must read both kinds, and must
    still treat a miss as possibly-unrecorded rather than certainly-unsaid.

    ``since_tool_result`` stops at the last user-role record of ANY kind, a tool result included: the
    thought that led to the call a PreToolUse guard is judging. That thought is on disk when the hook
    runs (measured 2026-10-21: tool_use record 46581 at 11:45:31.081, its PreToolUse rows from .596).
    Read from the END of the file, so a 765 MB transcript costs the turn's few KB.
    """
    chunks: list[str] = []
    try:
        with open(transcript_path, "rb") as fh:
            for raw in _lines_backward(fh):
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if rec.get("type") == "user" or rec.get("role") == "user":
                    content = rec.get("message", rec).get("content", "")
                    if not since_tool_result and isinstance(content, list) and any(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                    ):
                        continue
                    break
                if rec.get("type") != "assistant" and rec.get("role") != "assistant":
                    continue
                content = rec.get("message", rec).get("content", "")
                if isinstance(content, str):
                    chunks.append(content)
                    continue
                if not isinstance(content, list):
                    continue
                for block in reversed(content):
                    if not isinstance(block, dict):
                        continue
                    body = block.get("text") if block.get("type") == "text" else block.get("thinking")
                    if body:
                        chunks.append(str(body))
    except Exception:
        return ""
    return "\n\n".join(reversed(chunks))


def turn_tool_uses(transcript_path: str, names: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """EVERY tool_use block since the last user turn, oldest first, optionally filtered by name.

    Added 2026-08-09 for `dry_admission_guard`. Prose scanning cannot see the failure it judges:
    a DRY violation is admitted in a COMMENT inside an `Edit`, and the turn's chat text may never
    mention it. Reading the edits is the difference between a guard that watches what I SAY and
    one that watches what I WROTE.

    Returns the raw ``{"name": ..., "input": {...}}`` dicts so callers pick their own fields —
    `Edit` uses `new_string`, `Write` uses `content`, and inventing a common shape here would
    just move the parsing into a place that cannot see the tool's contract.

    Fails silent (empty list), same contract as the rest of this module.
    """
    uses: list[dict[str, Any]] = []
    for rec in records_backward(transcript_path):
        if rec.get("type") == "user" or rec.get("role") == "user":
            # A tool RESULT is delivered as a user-role record; only a real user message ends
            # the turn. Without this the scan stops at the first tool call it finds.
            content = rec.get("message", rec).get("content", "")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            break
        if rec.get("type") != "assistant" and rec.get("role") != "assistant":
            continue
        content = rec.get("message", rec).get("content", "")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if names and block.get("name") not in names:
                continue
            uses.append(block)
    return list(reversed(uses))


def _owner_text(rec: dict[str, Any]) -> str | None:
    """The owner's words in a record: a real user message (not a tool result), or a message he sent MID-TURN, which
    Claude Code stores as an attachment of type queued_command; None for anything else."""
    if rec.get("type") == "attachment":
        att = rec.get("attachment") or {}
        if not isinstance(att, dict) or att.get("type") != "queued_command":
            return None
        prompt = att.get("prompt", "")
        if isinstance(prompt, list):
            return " ".join(str(b.get("text", "")) for b in prompt if isinstance(b, dict))
        return str(prompt)
    if rec.get("type") != "user" and rec.get("role") != "user":
        return None
    content = rec.get("message", rec).get("content", "")
    if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    return _block_text(rec.get("message", rec))


def turn_events(transcript_path: str, *, visible_only: bool = False) -> list[tuple[str, object]]:
    """The turn IN ORDER, oldest first: ("owner", text) for the message that opened it and every message the owner sent
    mid-turn, ("prose", text) for each assistant text or thinking block, ("tool", block) for each tool_use block.

    Added 2026-10-17 for priority order (owner_first_guard via _priority_order): "which came first" -- a defect named,
    the owner's demand, then a lesser action -- is a question about ORDER, and the readers above each return one kind.
    ``visible_only`` drops thinking blocks (2026-10-28, _announced_order): a promise is what the owner READ, never a
    plan in the reasoning. Fails silent (empty list), same contract as the rest of this module.
    """
    events: list[tuple[str, object]] = []
    for rec in records_backward(transcript_path):
        owner = _owner_text(rec)
        if owner is not None:
            events.append(("owner", owner))
            if rec.get("type") != "attachment":
                break  # the real user message opened this turn
            continue
        if rec.get("type") != "assistant" and rec.get("role") != "assistant":
            continue
        content = rec.get("message", rec).get("content", "")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        for block in reversed(blocks if isinstance(blocks, list) else []):
            if not isinstance(block, dict) or (visible_only and block.get("type") == "thinking"):
                continue
            body = block.get("text") if block.get("type") == "text" else block.get("thinking")
            if block.get("type") == "tool_use":
                events.append(("tool", block))
            elif body:
                # a `thinking` block too: MEASURED 2026-10-17, the very sentence this reader exists for ("... would skip
                # it -- but first I'll handle the line-length issue") was stored ONLY as a thinking summary (turn_prose).
                events.append(("prose", str(body)))
    return list(reversed(events))


def last_assistant_text(transcript_path: str) -> str:
    """Text of the LAST assistant message in the JSONL transcript, or "" on any problem.

    Fails silent by design: a Stop hook that raises would wedge the session, and a guard that
    cannot read the transcript must let the turn through rather than block on nothing.
    """
    for rec in records_backward(transcript_path):
        if rec.get("type") != "assistant" and rec.get("role") != "assistant":
            continue
        msg = rec.get("message", rec)
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        return ""
    return ""
