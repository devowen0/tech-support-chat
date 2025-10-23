import sys
import subprocess
import json
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QHBoxLayout, QLabel, QMessageBox,
    QToolButton
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QOperatingSystemVersion
from PySide6.QtGui import QTextCursor, QIcon, QFontMetrics, QTextOption, QPalette, QColor
import random
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(APP_DIR, "logo.png")
LIGHT_ICON_PATH = os.path.join(APP_DIR, "dark-mode.svg")
DARK_ICON_PATH = os.path.join(APP_DIR, "light-mode.svg")

BOT_NAMES = ["Elsa", "Alma", "Freja", "Linnea", "Klara", "Elin",
             "Axel", "Leo", "Emil", "Nils", "Erik", "Johan",
             "Robin", "Alex", "Sam", "Kim", "Mika", "Lukas", "Svea"]
             
WELCOME_MESSAGES = [
    "👋 Hello there! I’m your Tech Support Assistant. How can I help you today?",
    "Hi! I’m here to help troubleshoot issues and answer your tech questions.",
    "Welcome! Need help fixing something or just have a quick tech question? I’m ready.",
    "Hi! I’m here to make tech support easy — what can I help you with today?",
]

BOT_NAME = random.choice(BOT_NAMES)

def is_system_dark_mode():
    """Try to detect if the OS is using dark mode."""
    app = QApplication.instance()
    palette = app.palette()
    bg_color = palette.color(QPalette.Window)
    text_color = palette.color(QPalette.WindowText)

    # Heuristic: if background is darker than text, assume dark mode
    return bg_color.value() < text_color.value()

# --- CONFIG ---
MODEL = "deepseek-v3.1:671b-cloud"  # Ollama model (cloud) deepseek-v3.1:671b-cloud
PROMPT = """You are a tech support agent.
Your job:
- Help users with technical issues they have.
- If they have any questions about how to do something, tell them step by step how to do it.
- Don't give any harmful or illegal advice.

Format your response in plain text. Keep it short and conversational.
"""
# typing speeds (ms)
TYPING_DOTS_INTERVAL_MS = 250
REVEAL_CHAR_INTERVAL_MS = 18
MODEL_TIMEOUT = 120  # seconds for subprocess


# --- Model worker ---
class ModelWorker(QThread):
    result_ready = Signal(str)
    error = Signal(str)

    def __init__(self, user_input: str):
        super().__init__()
        self.user_input = user_input

    def run(self):
        try:
            # We append to global conversation_history in ChatWindow, not here.
            full_prompt = PROMPT + "\n\n" + "\n".join(conversation_history) + f"\n{BOT_NAME}:"
            cmd = f"echo {json.dumps(full_prompt)} | ollama run {MODEL}"
            # increase timeout for cloud model
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=MODEL_TIMEOUT)
            output = result.stdout or ""
            output = output.strip()

            # Try to decode JSON-style escape sequences (\uXXXX). If that fails, use the raw output.
            try:
                # Wrap in quotes to let json.loads interpret escapes
                output_decoded = json.loads(f'"{output}"')
            except Exception:
                output_decoded = output

            if not output_decoded:
                self.error.emit("Error: Model returned no output.")
                return

            self.result_ready.emit(output_decoded)

        except subprocess.TimeoutExpired:
            self.error.emit("Error: Model timed out.")
        except FileNotFoundError:
            self.error.emit("Error: 'ollama' not found. Please install or run Ollama.")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


# --- Utility: simple markdown -> HTML ---
def markdown_to_html(text: str) -> str:
    """Convert basic Markdown-like elements to HTML:
       - **bold**
       - *italic*
       - - bullet lists (lines starting with -, *, or numbered)
       - code in backticks `code`
       - preserve newlines as <br>
    """
    if not text:
        return ""

    # Escape HTML special chars first
    text = (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))

    # inline code `code`
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # italic *text*
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

    # Convert list lines starting with -, * or numbered lists into <ul>/<ol>
    lines = text.splitlines()
    out_lines = []
    in_ul = False
    in_ol = False
    li_ul_re = re.compile(r'^\s*[-\*]\s+(.*)')
    li_ol_re = re.compile(r'^\s*\d+\.\s+(.*)')
    for line in lines:
        m_ul = li_ul_re.match(line)
        m_ol = li_ol_re.match(line)
        if m_ul:
            if not in_ul:
                out_lines.append("<ul style='margin:6px 0 6px 18px;padding:0;'>")
                in_ul = True
            out_lines.append(f"<li>{m_ul.group(1)}</li>")
            continue
        elif m_ol:
            if not in_ol:
                out_lines.append("<ol style='margin:6px 0 6px 18px;padding:0;'>")
                in_ol = True
            out_lines.append(f"<li>{m_ol.group(1)}</li>")
            continue
        else:
            if in_ul:
                out_lines.append("</ul>")
                in_ul = False
            if in_ol:
                out_lines.append("</ol>")
                in_ol = False
            out_lines.append(line)

    if in_ul:
        out_lines.append("</ul>")
    if in_ol:
        out_lines.append("</ol>")

    text = "<br>".join(out_lines)
    return text


# --- Global conversation (for model prompt) ---
conversation_history = []  # string lines used for model context

class ExpandingTextEdit(QTextEdit):
    """QTextEdit that sends message on Enter, inserts newline with Shift+Enter."""
    send_message = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() == Qt.ShiftModifier:
                # Shift+Enter → insert a newline
                self.insertPlainText("\n")
            else:
                # Enter → send message
                self.send_message.emit()
        else:
            super().keyPressEvent(event)

# --- Main Chat Window ---
class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tech Support Chat")
        # sizing
        screen = QApplication.primaryScreen()
        geom = screen.availableGeometry()
        sw, sh = geom.width(), geom.height()
        win_w, win_h = int(sw * 0.65), int(sw * 0.80)
        self.resize(win_w, win_h)
        self.move((sw - win_w) // 2, (sh - win_h) // 2)
        self.setWindowIcon(QIcon(ICON_PATH))

        # Styling
        # --- THEME SETUP ---
        dark_mode = is_system_dark_mode()
        self.dark_mode = dark_mode

        if dark_mode:
            bg_color = "#17141C"
            text_color = "#E0E0E0"
            input_bg = "#1E1A24"
            input_border = "#2C2A33"
            button_bg = "#6D4AFF"
            button_hover = "#8266FF"
            user_color = "#FF80AB"
            bot_color = "#BB86FC"
        else:
            bg_color = "#F5F6F7"
            text_color = "#000000"
            input_bg = "#F3F3F3"
            input_border = "#CCCCCC"
            button_bg = "#6D4AFF"
            button_hover = "#8266FF"
            user_color = "#0066CC"
            bot_color = "#8a51d6"

        # Apply stylesheet dynamically
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{
                font-size:18px;
                font-weight:600;
                color:{text_color};
            }}
            QPushButton {{
                background-color:{button_bg};
                color:#FFFFFF;
                border:none;
                border-radius:8px;
                padding:8px 16px;
                font-size:16px;
                font-weight:600;
            }}
            QPushButton:hover {{ background-color:{button_hover}; }}

            QTextEdit {{
                background:transparent;
                border:none;
                font-size:16px;
                color:{text_color};
                selection-background-color:{button_bg};
                selection-color:#FFFFFF;
            }}

            QTextEdit#input_field {{
                background-color:{input_bg};
                color:{text_color};
                border:1px solid {input_border};
                border-radius:8px;
                padding:8px;
                font-size:16px;
            }}
        """)

        # Save theme colors for message rendering
        self.user_color = user_color
        self.bot_color = bot_color

        # layout & widgets
        main_layout = QVBoxLayout()
        self.header = QLabel("Tech Support")
        # --- Theme toggle button (top-right) ---
        self.theme_toggle_btn = QToolButton(self)
        self.theme_toggle_btn.setIcon(QIcon(DARK_ICON_PATH if dark_mode else LIGHT_ICON_PATH))
        self.theme_toggle_btn.setAutoRaise(True)
        self.theme_toggle_btn.setToolTip("Toggle Light/Dark Mode")
        self.theme_toggle_btn.clicked.connect(self.toggle_theme)
        self.theme_toggle_btn.setFixedSize(32, 32)  # size of the icon button
        self.theme_toggle_btn.move(self.width() - 40, 10)  # top-right corner
        self.theme_toggle_btn.show()
        self.header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.header)

        # container to center
        self.chat_container = QWidget()
        chat_layout = QVBoxLayout()
        chat_layout.setSpacing(12)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_container.setLayout(chat_layout)

        # chat display expands to fill vertical space
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setAttribute(Qt.WA_TranslucentBackground)
        chat_layout.addWidget(self.chat_display, stretch=1)  # <-- Add stretch=1 here

        # input row stays at bottom
        input_row = QWidget()
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_field = ExpandingTextEdit()
        self.input_field.setObjectName("input_field")
        self.input_field.send_message.connect(self.send_message)
        self.input_field.setMinimumHeight(40)
        self.input_field.setMaximumHeight(150)
        self.input_field.setFixedHeight(40)  # initial height
        self.input_field.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input_field.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.input_field.textChanged.connect(self.adjust_input_height)
        self.send_button = QPushButton("Send")
        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(self.send_button)
        input_row.setLayout(input_layout)

        chat_layout.addWidget(input_row)  # <-- no stretch, stays at bottom
        QTimer.singleShot(0, self.adjust_input_height)

        # center chat_container at 70% width
        # center chat_container at 70% width
        # --- Set maximum width and horizontal centering ---
        self.chat_container.setFixedWidth(int(self.width() * 0.7))

        h_layout = QHBoxLayout()
        h_layout.addStretch(1)
        h_layout.addWidget(self.chat_container)
        h_layout.addStretch(1)

        # --- Main vertical layout ---
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 40, 20, 40)  # top/bottom + sides
        main_layout.setSpacing(12)

        # Header centered
        main_layout.addWidget(self.header, alignment=Qt.AlignHCenter)

        # Stretch pushes chat container toward bottom
        #main_layout.addStretch(1)

        # Add chat container horizontally centered
        main_layout.addLayout(h_layout)

        self.setLayout(main_layout)

        # Add a bit of spacing at the top so header isn’t stuck
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(0, 40, 0, 40)  # top/bottom margins
        self.setLayout(main_layout)

        # signals
        #self.input_field.returnPressed.connect(self.send_message)
        self.send_button.clicked.connect(self.send_message)

        # internal message store (each is dict with sender and html)
        self.messages = []

        # typing indicator state
        self.typing_indicator_timer = QTimer()
        self.typing_indicator_timer.timeout.connect(self._advance_dots)
        self.typing_dots = 0
        self.typing_msg_index = None  # index in self.messages for indicator, None if not active

        # reveal animation state
        self.reveal_timer = QTimer()
        self.reveal_timer.timeout.connect(self._reveal_next_char)
        self.reveal_full_text = ""
        self.reveal_index = 0
        self.reveal_msg_index = None

        # model worker
        self.worker = None
        
        # --- Display a random welcome message from the bot ---
        # When showing the welcome message, treat the bot properly
        welcome_text = random.choice(WELCOME_MESSAGES)
        conversation_history.append(f"{BOT_NAME}: {welcome_text}")
        # Force sender to BOT_NAME so color is correct
        self.messages.append({'sender': BOT_NAME, 'html': self._create_message_block(BOT_NAME, markdown_to_html(welcome_text))})
        self._render_messages()

        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # keep theme toggle button in top-right corner
        self.theme_toggle_btn.move(self.width() - 40, 10)
        
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode

        # Update the icon
        new_icon = DARK_ICON_PATH if self.dark_mode else LIGHT_ICON_PATH
        self.theme_toggle_btn.setIcon(QIcon(new_icon))

        # Set colors for light or dark mode
        if self.dark_mode:
            bg_color = "#17141C"
            text_color = "#E0E0E0"
            input_bg = "#1E1A24"
            input_border = "#2C2A33"
            button_bg = "#6D4AFF"
            button_hover = "#8266FF"
            user_color = "#FF80AB"
            bot_color = "#BB86FC"
        else:
            bg_color = "#F5F6F7"
            text_color = "#000000"
            input_bg = "#F3F3F3"
            input_border = "#CCCCCC"
            button_bg = "#6D4AFF"
            button_hover = "#8266FF"
            user_color = "#0066CC"
            bot_color = "#9C27B0"

        # Apply stylesheet dynamically
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel {{
                font-size:18px;
                font-weight:600;
                color:{text_color};
            }}
            QPushButton {{
                background-color:{button_bg};
                color:#FFFFFF;
                border:none;
                border-radius:8px;
                padding:8px 16px;
                font-size:16px;
                font-weight:600;
            }}
            QPushButton:hover {{ background-color:{button_hover}; }}

            QTextEdit {{
                background:transparent;
                border:none;
                font-size:16px;
                color:{text_color};
                selection-background-color:{button_bg};
                selection-color:#FFFFFF;
            }}

            QTextEdit#input_field {{
                background-color:{input_bg};
                color:{text_color};
                border:1px solid {input_border};
                border-radius:8px;
                padding:8px;
                font-size:16px;
            }}
        """)

        # Re-render chat messages to update colors
        self._render_messages()
        
    def append_message(self, sender: str, text: str):
        """Add a new message (bot or user) to the chat and render it."""
        html = markdown_to_html(text)
        self.messages.append({
            'sender': sender,
            'html': self._create_message_block(sender, html)
        })
        self._render_messages()
        
    # ---------- Rendering ----------
    def _render_messages(self):
        """Render the self.messages list into chat_display as HTML and scroll to bottom."""
        html_blocks = []
        for m in self.messages:
            html_blocks.append(m['html'])
        full_html = "<div style='font-size:16px; line-height:1.4;'>" + "".join(html_blocks) + "</div>"
        # setHtml will replace content; we maintain messages[] so it's idempotent
        self.chat_display.setHtml(full_html)
        self._scroll_to_bottom()

    def _create_message_block(self, sender: str, inner_html: str) -> str:
        """Return an HTML block for a message with colored sender but no bubble."""
        sender_color = self.bot_color if sender == BOT_NAME else self.user_color
        block = (
            f"<div style='margin-top:12px; margin-bottom:12px;'>"
            f"<div style='font-weight:700; color:{sender_color}; margin-bottom:4px;'>{sender}:</div>"
            f"<div>{inner_html}</div>"  # just plain text, no background or padding
            f"</div>"
        )
        return block

    # ---------- Typing indicator (dots) ----------
    def _start_typing_indicator(self):
        """Append a typing indicator message and begin cycling dots."""
        # Append a message with initial empty dots
        indicator_html = self._create_message_block(BOT_NAME, " ")
        self.messages.append({'sender': BOT_NAME, 'html': indicator_html})
        self.typing_msg_index = len(self.messages) - 1
        self.typing_dots = 0
        self.typing_indicator_timer.start(TYPING_DOTS_INTERVAL_MS)
        self._render_messages()

    def _stop_typing_indicator(self):
        """Stop and remove typing indicator if present."""
        if self.typing_msg_index is None:
            return
        self.typing_indicator_timer.stop()
        # Remove the indicator message (it will be replaced by real content)
        # Keep index for insertion of reveal message
        idx = self.typing_msg_index
        # remove item
        if 0 <= idx < len(self.messages):
            self.messages.pop(idx)
        self.typing_msg_index = None
        self._render_messages()

    def _advance_dots(self):
        """Update the typing indicator dots in-place."""
        if self.typing_msg_index is None:
            return
        self.typing_dots = (self.typing_dots + 1) % 4  # 0..3
        dots = "." * self.typing_dots
        inner_html = f"<span style='opacity:0.95;'> {dots} </span>"
        block = self._create_message_block(BOT_NAME, inner_html)
        # replace message at typing_msg_index
        if 0 <= self.typing_msg_index < len(self.messages):
            self.messages[self.typing_msg_index]['html'] = block
        else:
            # fallback: append and update index
            self.messages.append({'sender': '{BOT_NAME}', 'html': block})
            self.typing_msg_index = len(self.messages) - 1
        self._render_messages()

    # ---------- Reveal (character-by-character) ----------
    def _start_reveal(self, text: str):
        """Insert an empty block for {BOT_NAME} and start revealing characters into it."""
        html_safe = markdown_to_html(text)  # prepare HTML (we will reveal raw characters, but display as plain text inside bubble)
        # We'll reveal raw text (not HTML) but show escaped HTML later.
        # To simplify, reveal will operate on plain text; we convert to HTML when setting block.
        self.reveal_full_text = text
        self.reveal_index = 0
        # Insert placeholder message at end and remember index
        placeholder_html = self._create_message_block(BOT_NAME, "")
        self.messages.append({'sender': BOT_NAME, 'html': placeholder_html})
        self.reveal_msg_index = len(self.messages) - 1
        self.reveal_timer.start(REVEAL_CHAR_INTERVAL_MS)
        self._render_messages()

    def _reveal_next_char(self):
        if self.reveal_index >= len(self.reveal_full_text):
            self.reveal_timer.stop()
            self.reveal_full_text = ""
            self.reveal_index = 0
            self.reveal_msg_index = None
            return
        # extend reveal by one char
        self.reveal_index += 1
        partial = self.reveal_full_text[:self.reveal_index]
        # Convert to HTML for safe rendering (apply markdown conversion on the partial)
        partial_html = markdown_to_html(partial)
        block = self._create_message_block(BOT_NAME, partial_html)
        if 0 <= self.reveal_msg_index < len(self.messages):
            self.messages[self.reveal_msg_index]['html'] = block
        else:
            # append fallback
            self.messages.append({'sender': '{BOT_NAME}', 'html': block})
            self.reveal_msg_index = len(self.messages) - 1
        self._render_messages()

    # ---------- Helpers ----------
    def _scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ---------- Sending & response handling ----------
    def adjust_input_height(self):
        """Smoothly resize the input field based on content without shrinking too far."""
        doc = self.input_field.document()
        doc_height = doc.size().height()
        margins = self.input_field.contentsMargins()
        new_height = int(doc_height + margins.top() + margins.bottom() + 8)

        min_height = 40
        max_height = 150

        # prevent jumpy behavior on first input
        if new_height < min_height:
            new_height = min_height

        self.input_field.setFixedHeight(min(new_height, max_height))
        
    def send_message(self):
        user_input = self.input_field.toPlainText().strip()
        if not user_input:
            return
        # add to conversation model context
        conversation_history.append(f"User: {user_input}")

        # add to UI
        user_html = markdown_to_html(user_input)
        self.messages.append({'sender': 'You', 'html': self._create_message_block("You", user_html)})
        self._render_messages()

        # clear + disable input
        # clear + disable input
        self.input_field.clear()
        self.input_field.setFixedHeight(40)  # reset to default height
        self.input_field.setDisabled(True)
        self.send_button.setDisabled(True)

        # start typing indicator
        self._start_typing_indicator()

        # kick off model worker
        self.worker = ModelWorker(user_input)
        self.worker.result_ready.connect(self.display_response)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_response(self, response_text: str):
        # stop indicator and replace with reveal of response
        self._stop_typing_indicator()

        # sanitize response_text: strip any leading '{BOT_NAME}:' if model included it
        if response_text.strip().lower().startswith(f"{BOT_NAME.lower()}:"):
            response_text = response_text.split(":", 1)[1].strip()

        # add response to conversation_history for future context
        conversation_history.append(f"{BOT_NAME}: {response_text}")

        # start reveal animation (character by character)
        self._start_reveal(response_text)

        # re-enable input (user can type while reveal continues)
        self.input_field.setDisabled(False)
        self.send_button.setDisabled(False)
        self.input_field.setFocus()

    def display_error(self, error_message: str):
        # stop any typing indicator
        self._stop_typing_indicator()
        QMessageBox.warning(self, "Error", error_message)
        self.input_field.setDisabled(False)
        self.send_button.setDisabled(False)
        self.input_field.setFocus()

    def keyPressEvent(self, event):
        """Redirect key presses to the input_field when it's not focused."""
        # Ignore modifier-only keys (like Shift, Ctrl, etc.)
        if not event.text():
            super().keyPressEvent(event)
            return

        # If the input field isn't focused, focus it and forward the key press
        if not self.input_field.hasFocus():
            self.input_field.setFocus()
            QApplication.sendEvent(self.input_field, event)
        else:
            super().keyPressEvent(event)

# --- Run app ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(ICON_PATH))
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())
