"""
Textual User Interface. Demo program.

With a menu and 2 panels, side by side.
In the left one, a YAML editor, in the right one, a preview of the parsed YAML as JSON

This is a demo program, not meant to be used in production.
The YAML is validated each 3 seconds, and the JSON preview is updated.
If errors are found, they are displayed in the JSON panel.
With info in about the error type and line number.

The YAML editor has syntax highlighting, line numbers, and a status bar
The yaml is persisted in a file in the program directory.


It uses the Textual library: https://textual.textualize.io/


"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from rich.panel import Panel
from rich.syntax import Syntax as RichSyntax

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static, TextArea


YAML_FILE = Path(__file__).with_name("demo.yaml")


def _json_default(value: Any) -> Any:
	"""Fallback serializer for objects not supported by json.dumps."""
	if isinstance(value, (datetime, date)):
		return value.isoformat()
	if isinstance(value, set):
		return sorted(value)
	return str(value)


class MenuHintBar(Static):
	"""Displays keyboard shortcuts as a faux menu bar."""

	def on_mount(self) -> None:
		self.update(
			"[b]Menu[/b]  "
			"[i]Ctrl+S[/i] Save  |  "
			"[i]Ctrl+R[/i] Reload  |  "
			"[i]Ctrl+Q[/i] Quit  |  "
			"[i]Ctrl+F[/i] Format  |  "
			"[i]F5[/i] Validate"
		)


class StatusBar(Static):
	"""Simple status bar that shows caret position and validation state."""

	cursor_text: reactive[str] = reactive("Ln 1, Col 1")
	message_text: reactive[str] = reactive("Ready")

	def compose(self) -> ComposeResult:  # type: ignore[override]
		yield Static(id="cursor", expand=False)
		yield Static(id="message", expand=True)

	def on_mount(self) -> None:
		self.update_contents()

	def update_position(self, row: int, column: int) -> None:
		self.cursor_text = f"Ln {row + 1}, Col {column + 1}"
		self.update_contents()

	def update_message(self, message: str) -> None:
		self.message_text = message
		self.update_contents()

	def update_contents(self) -> None:
		cursor_widget = self.query_one("#cursor", Static)
		cursor_widget.update(self.cursor_text)
		message_widget = self.query_one("#message", Static)
		message_widget.update(self.message_text)


class PreviewPanel(ScrollableContainer):
	"""Displays either the JSON preview or YAML errors."""

	DEFAULT_CSS = """
	PreviewPanel {
		overflow-y: auto;
		overflow-x: hidden;
	}

	PreviewPanel > Static {
		padding: 0;
	}
	"""

	can_focus = True

	def compose(self) -> ComposeResult:
		self._body = Static(expand=True)
		yield self._body

	def show_json(self, data: str) -> None:
		syntax = RichSyntax(
			data,
			"json",
			theme="monokai",
			line_numbers=True,
			word_wrap=False,
		)
		panel = Panel(syntax, title="JSON Preview", border_style="cyan")
		self._body.update(panel)
		self.remove_class("error")
		self.scroll_home(animate=False)

	def show_error(self, error: Exception) -> None:
		error_type = type(error).__name__
		line_info = ""
		if isinstance(error, yaml.YAMLError):
			mark = getattr(error, "problem_mark", None)
			if mark is not None:
				line_info = f" (line {mark.line + 1}, column {mark.column + 1})"
		message = (
			"[bold red]YAML Error[/bold red]\n\n"
			f"[yellow]{error_type}{line_info}[/yellow]\n\n"
			f"{error}"
		)
		panel = Panel(message, title="Validation", border_style="red")
		self._body.update(panel)
		self.add_class("error")
		self.scroll_home(animate=False)


class YAMLValidated(Message):
	"""Message emitted after validation run."""

	def __init__(self, success: bool, error: Optional[Exception] = None) -> None:
		self.success = success
		self.error = error
		super().__init__()


class YAMLEditorApp(App):
	"""Main Textual application implementing the YAML editor demo."""

	CSS = """
	Screen {
		layout: vertical;
	}

	Horizontal {
		height: 1fr;
	}

	#content {
		height: 1fr;
	}

	#editor {
		border: solid green;
		width: 1fr;
		min-width: 40;
		background: $surface-darken-2;
		color: $text;
	}

	#preview {
		border: solid blue;
		padding: 1 2;
		overflow: auto;
		width: 1fr;
		min-width: 40;
		background: $surface-darken-1;
	}

	#preview.error {
		border: solid $error;
	}

	#status-bar {
		dock: bottom;
		height: 1;
		background: $surface;
		color: $text-muted;
	}

	#status-bar Static {
		padding: 0 1;
	}
	"""

	TITLE = "YAML Editor Demo"
	BINDINGS = [
		Binding("ctrl+s", "save_yaml", "Save"),
		Binding("ctrl+r", "reload_yaml", "Reload"),
		Binding("ctrl+f", "format_yaml", "Format"),
		Binding("ctrl+q", "quit", "Quit"),
		Binding("f5", "validate_now", "Validate"),
	]

	preview_panel: PreviewPanel
	yaml_editor: TextArea
	status_bar: StatusBar

	def compose(self) -> ComposeResult:
		yield Header()
		yield MenuHintBar(id="menu-bar")
		with Container(id="content"):
			with Horizontal():
				self.yaml_editor = TextArea(
					language="yaml",
					show_line_numbers=True,
					theme="dracula",
					id="editor",
				)
				yield self.yaml_editor
				self.preview_panel = PreviewPanel(id="preview")
				yield self.preview_panel
		self.status_bar = StatusBar(id="status-bar")
		yield self.status_bar
		yield Footer()

	async def on_mount(self) -> None:
		self._ensure_yaml_file()
		self._load_yaml()
		self.set_interval(3.0, self._validate_yaml, name="validator")

	async def on_textarea_changed(self, event: TextArea.Changed) -> None:  # type: ignore[override]
		self.status_bar.update_message("Modified (unsaved)")

	async def on_textarea_cursor_moved(self, event: TextArea.CursorMoved) -> None:  # type: ignore[override]
		self.status_bar.update_position(event.cursor_location.row, event.cursor_location.column)

	def _ensure_yaml_file(self) -> None:
		if not YAML_FILE.exists():
			YAML_FILE.write_text("# Start editing YAML here\n", encoding="utf-8")

	def _load_yaml(self) -> None:
		self.yaml_editor.load_text(YAML_FILE.read_text(encoding="utf-8"))
		self.status_bar.update_message("Loaded")
		self._validate_yaml()

	def _validate_yaml(self) -> None:
		text = self.yaml_editor.text
		try:
			parsed = yaml.safe_load(text) if text.strip() else None
			json_output = (
				json.dumps(parsed, indent=2, ensure_ascii=False, default=_json_default)
				if parsed is not None
				else "null"
			)
			self.preview_panel.show_json(json_output)
			self.status_bar.update_message("YAML valid")
			self.save_yaml(write_status=False)
			self.post_message(YAMLValidated(True))
		except Exception as error:  # pylint: disable=broad-except
			self.preview_panel.show_error(error)
			self.status_bar.update_message("YAML invalid")
			self.post_message(YAMLValidated(False, error))

	def action_save_yaml(self) -> None:
		self.save_yaml()

	def save_yaml(self, write_status: bool = True) -> None:
		YAML_FILE.write_text(self.yaml_editor.text, encoding="utf-8")
		if write_status:
			self.status_bar.update_message("Saved")

	def action_reload_yaml(self) -> None:
		self._load_yaml()

	def action_format_yaml(self) -> None:
		try:
			data = yaml.safe_load(self.yaml_editor.text)
		except yaml.YAMLError:
			return
		if data is None:
			formatted = ""
		else:
			formatted = yaml.safe_dump(data, sort_keys=False)
		self.yaml_editor.load_text(formatted)
		self.status_bar.update_message("Formatted")

	def action_clear_yaml(self) -> None:
		self.yaml_editor.load_text("")
		self.status_bar.update_message("Cleared")

	def action_show_about(self) -> None:
		self.status_bar.update_message("Textual YAML Demo – https://textual.textualize.io")

	def action_validate_now(self) -> None:
		self._validate_yaml()


if __name__ == "__main__":
	YAMLEditorApp().run()
