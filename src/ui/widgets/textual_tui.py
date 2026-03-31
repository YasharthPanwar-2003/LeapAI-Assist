from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Input, Label

from src.core.orchestrator import Orchestrator
from src.logger import get_logger
from src.os_integration.system_context import SystemContext
from src.os_integration.version_detector import VersionDetector
from src.ui.widgets.chat_panel import ChatPanel
from src.ui.widgets.onboarding_panel import OnboardingPanel
from src.ui.widgets.status_bar import StatusBar

logger = get_logger(__name__)

_HELP_TEXT = """\
[bold]Keyboard shortcuts[/bold]
  Ctrl+Q   Quit the application
  Ctrl+R   Reset chat history
  Ctrl+O   Toggle onboarding panel
  Ctrl+L   Clear chat display
  F1       Show this help

[bold]Example queries[/bold]
  "How do I install nginx using zypper?"
  "What is Cockpit and how do I access it?"
  "Show me failed systemd services"
  "How do I add a new zypper repository?"
"""


class SuseAIApp(App):
    """
    Main Textual TUI application for the openSUSE AI Assistant.

    Features:
        - Real-time async token streaming (Architecture Section 8)
        - Keyboard navigation (Architecture Section 10)
        - ~20 MB RAM footprint (Architecture Section 10)
        - SSH-compatible terminal rendering (Architecture Section 10)
    """

    CSS_PATH = "styles/theme.tcss"

    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
    }

    #input-container {
        height: 5;
        border: solid $primary-lighten-2;
        padding: 1;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+r", "reset", "Reset Chat"),
        ("ctrl+o", "toggle_onboarding", "Onboarding"),
        ("ctrl+l", "clear_chat", "Clear"),
        ("f1", "help", "Help"),
    ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self.orchestrator: Orchestrator | None = None
        self.version_detector = VersionDetector()
        self.system_context = SystemContext()
        self._version_info: dict = {}

    def compose(self) -> ComposeResult:
        """Compose TUI layout."""
        yield Header()
        yield Container(
            OnboardingPanel(id="onboarding-container"),
            ChatPanel(id="chat-panel"),
            StatusBar(id="status-bar"),
            id="main-container",
        )
        yield Container(
            Label("Enter your question (Ctrl+Q to quit):"),
            Input(
                placeholder="e.g. How do I install nginx using zypper?",
                id="query-input",
            ),
            id="input-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialise the TUI after all widgets are mounted."""
        self.orchestrator = Orchestrator()

        chat = self.query_one("#chat-panel", ChatPanel)
        status = self.query_one("#status-bar", StatusBar)
        onboarding = self.query_one("#onboarding-container", OnboardingPanel)
        inp = self.query_one("#query-input", Input)

        # Detect OS version
        self._version_info = self.version_detector.detect()
        ver = self._version_info
        logger.info("Detected: %s %s", ver["pretty_name"], ver["version_id"])

        onboarding.version = ver["version_id"]
        status.update_os_version(ver["pretty_name"], ver["management_tool"])
        status.update_rag_backend(self.orchestrator.config.rag_backend)
        inp.focus()

        await chat.add_message(
            "system",
            f"Welcome to openSUSE AI Assistant!\n"
            f"System:     {ver['pretty_name']} {ver['version_id']}\n"
            f"Management: {ver['management_tool']}\n"
            f"Type a question below, or press Ctrl+O for guided onboarding.",
        )

        logger.debug("SuseAIApp mounted")

    async def on_unmount(self) -> None:
        """Clean up orchestrator on exit."""
        if self.orchestrator:
            await self.orchestrator.close()
        logger.info("SuseAIApp unmounted")

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user pressing Enter in the query input box."""
        query = event.value.strip()
        if not query:
            return

        event.input.value = ""

        chat = self.query_one("#chat-panel", ChatPanel)
        status = self.query_one("#status-bar", StatusBar)

        await chat.add_message("user", query)
        status.update_status("Thinking…")

        if self.orchestrator:
            try:
                # Await the async function to unwrap the generator
                response_stream = await self.orchestrator.process_query(query, stream=True)
                # Cast to satisfy Pylance (process_query returns str | AsyncGenerator)
                await chat.stream_response(cast(AsyncIterator[str], response_stream))
                status.update_status("Ready")
            except Exception as exc:
                logger.error("Query processing failed: %s", exc)
                await chat.add_message("system", f"⚠️ Error: {exc}")
                status.update_status("Error")

    def on_onboarding_panel_topic_selected(self, event: OnboardingPanel.TopicSelected) -> None:
        """Wire topic row click → pre-fill the query input."""
        inp = self.query_one("#query-input", Input)
        inp.value = event.prompt
        inp.focus()
        logger.debug("Onboarding topic selected: %s", event.key)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_quit(self) -> None:
        """Quit the application."""
        logger.info("User quit application")
        self.exit()

    def action_reset(self) -> None:
        """Reset chat history and token counters."""
        if self.orchestrator:
            self.orchestrator.session.history.clear()
            self.orchestrator.session.token_count = 0

        self.query_one("#chat-panel", ChatPanel).clear()
        self.query_one("#status-bar", StatusBar).reset()
        logger.debug("Chat reset by user")

    def action_clear_chat(self) -> None:
        """Clear chat display only (keeps history in orchestrator)."""
        self.query_one("#chat-panel", ChatPanel).clear()

    def action_toggle_onboarding(self) -> None:
        """Toggle the onboarding panel visibility."""
        ob = self.query_one("#onboarding-container", OnboardingPanel)
        ob.display = not ob.display
        logger.debug("Onboarding panel toggled (visible=%s)", ob.display)

    def action_help(self) -> None:
        """Show help in the chat panel."""

        async def _show_help() -> None:
            await self.query_one("#chat-panel", ChatPanel).add_message("system", _HELP_TEXT)

        self.run_worker(_show_help(), exclusive=False)


def main() -> None:
    """Launch the Textual TUI."""
    SuseAIApp().run()


if __name__ == "__main__":
    main()
