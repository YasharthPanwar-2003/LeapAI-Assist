from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import DataTable, Label

from src.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pre-built prompt strings (version-agnostic; the TUI can refine further)
# ---------------------------------------------------------------------------
ONBOARDING_PROMPTS: dict[str, str] = {
    "welcome": "Welcome me to openSUSE and give me a brief overview.",
    "package_management": "Explain how package management works with zypper. Show the most common commands.",
    "yast": "What is YaST and how do I use it for system administration?",
    "cockpit": "What is Cockpit and how do I access it on my system?",
    "repositories": "How do repositories work in openSUSE? How do I add, remove, and manage them?",
    "firewall": "How do I configure the firewall on openSUSE?",
    "updates": "How do I keep my system up to date? Explain the full update process.",
    "troubleshooting": "What are the most common troubleshooting steps when something goes wrong?",
}


class OnboardingPanel(Container):
    """
    Guided onboarding topics panel.

    Features:
        - Pre-built prompts for common getting-started flows
        - Version-aware rows (YaST for Leap 15.x, Cockpit for Leap 16+)
        - Click any row to fire ``OnboardingPanel.TopicSelected``

    Usage::

        # In compose():
        yield OnboardingPanel(version="16.0", id="onboarding-container")

        # In parent app:
        def on_onboarding_panel_topic_selected(
            self, event: OnboardingPanel.TopicSelected
        ) -> None:
            self.input_widget.value = event.prompt
    """

    # ------------------------------------------------------------------
    # Custom message
    # ------------------------------------------------------------------
    @dataclass
    class TopicSelected(Message):
        """Fired when the user clicks / activates a topic row."""

        key: str  # e.g. "package_management"
        prompt: str  # the full canned prompt string

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------
    DEFAULT_CSS = """
    OnboardingPanel {
        height: auto;
        max-height: 14;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }

    OnboardingPanel #ob-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    """

    def __init__(self, version: str = "16.0", **kwargs: Any) -> None:
        """
        Args:
            version: openSUSE VERSION_ID string (e.g. ``"15.6"`` or ``"16.0"``).
                     Determines which tool-set is emphasised in the topic list.
            **kwargs: Forwarded to ``Container.__init__`` (important: allows
                      callers to pass ``id=``, ``classes=``, etc.).
        """
        super().__init__(**kwargs)
        self.version = version
        self._table: DataTable | None = None
        # ✅ FIX: Store the ColumnKey for the first column to avoid integer indexing
        self._key_col_key: Any = None

    def compose(self) -> ComposeResult:
        """Compose onboarding widgets."""
        yield Label("📚 Guided Onboarding Topics", id="ob-title")
        yield DataTable(id="ob-table", cursor_type="row", show_header=True)

    def on_mount(self) -> None:
        """Populate the DataTable after mount."""
        self._table = self.query_one("#ob-table", DataTable)
        # ✅ FIX: Capture the ColumnKey returned by add_columns
        self._key_col_key, _ = self._table.add_columns("Key", "Description")

        for key, desc in self._version_aware_topics().items():
            # FIX: plain strings — no inline Rich markup in DataTable cells
            self._table.add_row(key, desc[:72])

        logger.debug("OnboardingPanel mounted (version=%s)", self.version)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Fire TopicSelected when the user presses Enter or clicks a row."""
        if self._table is None:
            return

        row_key = event.row_key
        # ✅ FIX: Use the saved ColumnKey instead of self._table.columns[0].key
        key_cell = self._table.get_cell(row_key, self._key_col_key)
        key = str(key_cell)
        prompt = ONBOARDING_PROMPTS.get(key, "")
        if prompt:
            self.post_message(self.TopicSelected(key=key, prompt=prompt))
            logger.debug("OnboardingPanel topic selected: %s", key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _version_aware_topics(self) -> dict[str, str]:
        """
        Return the topic dict filtered for the detected openSUSE version.

        Architecture Section 6: Version-aware tool mapping.
        """
        if self.version.startswith("15."):
            return {
                "welcome": f"Welcome to openSUSE Leap {self.version}",
                "package_management": "zypper + YaST Software module",
                "yast": "YaST control centre guide",
                "repositories": "YaST Software Repositories",
                "firewall": "YaST Firewall module",
                "updates": "YaST Online Update",
                "troubleshooting": "YaST logs + journalctl",
            }
        else:
            return {
                "welcome": f"Welcome to openSUSE Leap {self.version}",
                "package_management": "zypper + Myrlyn GUI",
                "cockpit": "Cockpit web UI (localhost:9090)",
                "repositories": "Cockpit + zypper repos",
                "firewall": "Cockpit Firewall + firewall-cmd",
                "updates": "zypper dup + Cockpit updates",
                "troubleshooting": "Cockpit Logs + journalctl",
            }

    def get_topic_prompt(self, topic_key: str) -> str | None:
        """
        Return the canned prompt for *topic_key*, or ``None`` if not found.

        Args:
            topic_key: One of the keys in ``ONBOARDING_PROMPTS``.
        """
        return ONBOARDING_PROMPTS.get(topic_key)
