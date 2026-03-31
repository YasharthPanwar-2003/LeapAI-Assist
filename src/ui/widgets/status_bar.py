from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label

from src.logger import get_logger

logger = get_logger(__name__)


class StatusBar(Horizontal):
    """
    Docked status bar showing OS version, token budget, KV cache and RAG info.

    Features:
        - OS version display (Leap 15.x → YaST, Leap 16+ → Cockpit)
        - Token budget: ``used / total (%)``
        - KV cache efficiency indicator (green ≥ 60 %, yellow < 60 %)
        - RAG backend indicator (Vectorless / Vector)
        - General status string ("Ready", "Thinking…", "Error")

    Usage::

        status = StatusBar()
        # After mount:
        status.update_os_version("openSUSE Leap 16.0", "Cockpit")
        status.update_tokens(used=2000, total=8192)
        status.update_kv_cache(0.65)
        status.update_rag_backend("vectorless")
        status.update_status("Ready")
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 3;
        border: solid $warning;
        padding: 0 1;
        background: $surface;
        dock: bottom;
    }

    StatusBar Label {
        margin: 0 1;
        padding: 0 1;
    }

    StatusBar .kv-good {
        color: $success;
        text-style: bold;
    }

    StatusBar .kv-poor {
        color: $warning;
        text-style: bold;
    }

    StatusBar .tokens-critical {
        color: $error;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # FIX: all five labels declared here so type-checkers and runtime agree
        self._version_label: Label | None = None
        self._token_label: Label | None = None
        self._kv_label: Label | None = None  # ← was missing in original
        self._rag_label: Label | None = None
        self._status_label: Label | None = None

    def compose(self) -> ComposeResult:
        """Compose the five status labels."""
        yield Label("OS: --", id="sb-version")
        yield Label("Tokens: 0/8192", id="sb-tokens")
        yield Label("KV Cache: --", id="sb-kv")
        yield Label("RAG: --", id="sb-rag")
        yield Label("Status: Ready", id="sb-status")

    def on_mount(self) -> None:
        """Cache label references after mount."""
        self._version_label = self.query_one("#sb-version", Label)
        self._token_label = self.query_one("#sb-tokens", Label)
        self._kv_label = self.query_one("#sb-kv", Label)  # ← FIX
        self._rag_label = self.query_one("#sb-rag", Label)
        self._status_label = self.query_one("#sb-status", Label)
        logger.debug("StatusBar mounted")

    # ------------------------------------------------------------------
    # Public update API
    # ------------------------------------------------------------------

    def update_os_version(self, version: str, tooling: str) -> None:
        """
        Update the OS version display.

        Args:
            version: Pretty name (e.g. ``"openSUSE Leap 16.0"``).
            tooling: Management tool (``"YaST"`` or ``"Cockpit"``).

        Architecture Section 6: YaST vs Agama tool mapping.
        """
        if self._version_label:
            self._version_label.update(f"OS: {version} ({tooling})")

    def update_tokens(self, used: int, total: int = 8192) -> None:
        """
        Update the token budget display.

        Args:
            used:  Tokens consumed in the current context window.
            total: Total context size (default: 8 192 for LFM2.5).

        Architecture Section 3: Context window zones.
        """
        if not self._token_label:
            return

        pct = (used / total) * 100 if total > 0 else 0.0
        self._token_label.update(f"Tokens: {used}/{total} ({pct:.0f}%)")

        # FIX: add/remove CSS class properly instead of always adding
        if pct > 90:
            self._token_label.add_class("tokens-critical")
        else:
            self._token_label.remove_class("tokens-critical")

    def update_kv_cache(self, efficiency: float) -> None:
        """
        Update the KV cache efficiency indicator.

        Args:
            efficiency: Cache hit ratio in ``[0.0, 1.0]``.

        Architecture Section 3: Expected 60-70 % KV cache efficiency.
        """
        if not self._kv_label:  # ← now safe: _kv_label is always set on mount
            return

        pct = efficiency * 100
        self._kv_label.update(f"KV Cache: {pct:.0f}%")

        if efficiency >= 0.6:
            self._kv_label.add_class("kv-good")
            self._kv_label.remove_class("kv-poor")
        else:
            self._kv_label.add_class("kv-poor")
            self._kv_label.remove_class("kv-good")

    def update_rag_backend(self, backend: str) -> None:
        """
        Update the RAG backend indicator.

        Args:
            backend: ``"vectorless"`` or ``"vector"``.

        Architecture Section 5: RAG plug-and-play.
        """
        if self._rag_label:
            label = "Vectorless" if backend == "vectorless" else "Vector"
            self._rag_label.update(f"RAG: {label}")

    def update_status(self, status: str) -> None:
        """
        Update the free-form status string.

        Args:
            status: Human-readable status (e.g. ``"Ready"``, ``"Thinking…"``).
        """
        if self._status_label:
            self._status_label.update(f"Status: {status}")

    def reset(self) -> None:
        """Reset all status fields to their defaults."""
        if self._token_label:
            self._token_label.update("Tokens: 0/8192")
            self._token_label.remove_class("tokens-critical")
        if self._kv_label:  # ← FIX: safe now
            self._kv_label.update("KV Cache: --")
            self._kv_label.remove_class("kv-good", "kv-poor")
        if self._rag_label:
            self._rag_label.update("RAG: --")
        if self._status_label:
            self._status_label.update("Status: Ready")
        logger.debug("StatusBar reset")
