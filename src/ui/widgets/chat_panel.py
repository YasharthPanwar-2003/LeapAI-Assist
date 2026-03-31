from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Label, RichLog

from src.logger import get_logger

logger = get_logger(__name__)

# Role display configuration
_ROLE_CONFIG: dict[str, tuple[str, str]] = {
    "user": ("👤", "[bold cyan]"),
    "assistant": ("🤖", "[bold green]"),
    "system": ("⚙️", "[bold yellow]"),
}


class ChatPanel(ScrollableContainer):
    """
    Streaming chat display panel.

    Features:
        - Real-time async token streaming (llama.cpp SSE compatible)
        - Syntax-highlighted Rich markup output
        - RAG source citations from retrieval results
        - Auto-scroll to the latest message
        - Role-coloured headers (user/assistant/system)

    Usage::

        panel = ChatPanel()
        await panel.add_message("user", "How do I install nginx?")
        await panel.stream_response(token_async_generator)
        panel.add_source_citation([{"title": "zypper docs", "url": "...", "relevance": 0.9}])
    """

    DEFAULT_CSS = """
    ChatPanel {
        height: 1fr;
        border: solid $success;
        padding: 1;
        background: $surface;
    }

    ChatPanel #chat-title {
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }

    ChatPanel #chat-log {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._log: RichLog | None = None

    def compose(self) -> ComposeResult:
        """Compose chat panel widgets."""
        yield Label("🦎 openSUSE AI Assistant", id="chat-title")
        yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        """Cache the RichLog reference after mount."""
        self._log = self.query_one("#chat-log", RichLog)
        logger.debug("ChatPanel mounted")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_message(self, role: str, content: str) -> None:
        """
        Add a complete, pre-formed message to the chat log.

        Args:
            role:    One of ``'user'``, ``'assistant'``, or ``'system'``.
            content: Full message body (may contain Rich markup).

        Architecture Section 8, Step 7 — Response formatter.
        """
        if self._log is None:
            logger.warning("ChatPanel.add_message called before mount — skipping")
            return

        ts = datetime.now().strftime("%H:%M:%S")
        emoji, colour = _ROLE_CONFIG.get(role, ("💬", "[bold]"))

        # Escape square-brackets in *content* so Rich does not mis-parse them
        safe_content = content.replace("[", r"\[")

        header = f"[dim]{ts}[/dim] {colour}{emoji} {role.title()}:[/]\n"
        self._log.write(header + safe_content)
        self._log.scroll_end(animate=False)

        logger.debug("Chat message added (role=%s, len=%d)", role, len(content))

    async def stream_response(self, tokens: AsyncIterator[str]) -> None:
        """
        Stream LLM tokens into the chat log in real-time.

        Args:
            tokens: Async generator yielding string tokens one-by-one.

        Architecture Section 8, Steps 6-7 — llama.cpp streaming.
        """
        if self._log is None:
            logger.warning("ChatPanel.stream_response called before mount — skipping")
            return

        ts = datetime.now().strftime("%H:%M:%S")
        header = f"[dim]{ts}[/dim] [bold green]🤖 Assistant:[/]\n"
        self._log.write(header)

        async for token in tokens:
            # Escape Rich markup special characters in raw LLM output
            safe = token.replace("\\", "\\\\").replace("[", r"\[")
            self._log.write(safe)

        self._log.scroll_end(animate=False)
        logger.debug("Token streaming complete")

    def add_source_citation(self, sources: list[dict]) -> None:
        """
        Append RAG source citations below the latest response.

        Args:
            sources: List of dicts with keys ``title``, ``url``, ``relevance``.

        Architecture Section 5: RetrievedChunk metadata.
        """
        if not self._log or not sources:
            return

        lines = ["\n[dim]📎 Sources:[/dim]"]
        for src in sources[:3]:
            title = src.get("title", "Unknown")
            url = src.get("url", "")
            relevance = src.get("relevance", 0.0)
            pct = f"{relevance:.0%}"
            entry = f"[dim]  • {title} ({pct})"
            if url:
                entry += f" — {url}"
            entry += "[/dim]"
            lines.append(entry)

        self._log.write("\n".join(lines))
        self._log.scroll_end(animate=False)

    def clear(self) -> None:
        """Clear all chat history from the display."""
        if self._log:
            self._log.clear()
            logger.debug("ChatPanel cleared")
