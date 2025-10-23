# AI Tech Support Chat (PySide6 + Ollama)

A sleek, modern desktop chat app built with **PySide6 (Qt for Python)** that connects to a local or cloud **Ollama AI model** to simulate a friendly tech support assistant. Includes dark/light theme toggle, typing animations, and markdown rendering.

## Demo
<div align="center">
  <table>
    <tr>
      <th>Dark Mode</th>
      <th>Light Mode</th>
    </tr>
    <tr>
      <td><img src="screenshots/dark-mode.png" width="100"></td>
      <td><img src="screenshots/light-mode.png" width="100"></td>
    </tr>
  </table>
</div>

## Install dependencies
Install the required Python packages from requirements.txt:
```bash
pip install -r requirements.txt
```

## Run the app
Make sure Ollama is running (see the “Connecting Ollama” section), then start the desktop app:
```bash
python app.py
```

## Connecting Ollama

This app communicates with Ollama through a simple subprocess call — it sends the user’s message to the model and receives the AI’s response as plain text.

### 1. Install Ollama
If you haven’t already, install Ollama from [ollama.ai](https://ollama.ai).

For macOS:
```bash
brew install ollama
```
For Linux:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```
For Windows:
```bash
Download and install from https://ollama.com/download
```

### 2. Run Ollama
Start the Ollama service before running the chat app:
```bash
ollama serve
```

### 3. Pull a Model
Download the model you want to use — for example, mistral:7b or deepseek-v3.1:671b-cloud:
```bash
ollama pull mistral:7b
```
You can view available models at ollama.ai/library

### 4. Configure the Model
In app.py, locate this line:
```bash
MODEL = "deepseek-v3.1:671b-cloud"
```
Change it to the local model you pulled, if necessary.

## Features
- Interactive chat interface using PySide6
- AI responses via Ollama (configurable model, e.g., `deepseek-v3.1:671b-cloud`)
- Automatic and manual dark/light theme detection
- Smart input box (Shift+Enter for newline, Enter to send)
- Typing indicator and animated text reveal
- Conversation memory for model context
- Basic Markdown support (**bold**, *italic*, lists, `code`)

## How It Works
- User messages are sent to an `Ollama` subprocess using `subprocess.run`.
- The model’s response is received as plain text and displayed in the UI.
- The chat uses `QThread` to keep the UI responsive during model inference.
- Markdown formatting is converted to HTML for rich text display.
- The interface uses Qt’s stylesheet system for theming and color updates.

## UX Features
- Detects system dark/light mode automatically and lets users toggle themes manually with a clean icon button in the header.
- Simulates real human typing through character-by-character animation reveal.
- Use of distinct colors for user and AI names. 
- Supports bold, italic, bullet lists, and inline code for clear, structured answers.

## Future Improvements
- Add support for streaming model output
- Save chat history to file, and encrypt with AES-256-GCM
- Add settings page for choosing model & temperature

## Security Note
- Currently, this app does not store chat data. Future versions will support optional AES-256-GCM encryption for local chat history files.
- This app sends data to Deepseek servers to retrieve responses. Ollama supports models that run entirely locally, which will not expose any data to servers, such as mistral:7b, and this can be changed in the script by editing the line MODEL = "deepseek-v3.1:671b-cloud".


## Acknowledgments
- [Ollama](https://ollama.ai/) for model integration
- [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/) for GUI framework
- Icons by [freesvgicons](https://freesvgicons.com/)

## License
This project is licensed under the [MIT License](LICENSE).
