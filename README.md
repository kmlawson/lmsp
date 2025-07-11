# lmsp - LM Studio Prompt CLI

A simple command-line interface for sending prompts to LM Studio loaded models.

## Features

- Send prompts to locally loaded LM Studio models
- Uses the first loaded model by default (or specify with `-m`)
- **Requires pre-loaded models**: Models must be loaded using `lms load <model>` or LM Studio desktop app
- Support for piping input from other commands
- Verbose logging with `-v` flag for debugging
- Simple and fast command-line interface

## Installation

### Quick Install from PyPI (Recommended)
```bash
# Install globally with pip
pip install lmsp

# Or install globally with uv (recommended)
uv tool install lmsp
```

### Alternative Installation Methods

#### Install from source
```bash
# Using uv tool (recommended - installs globally)
uv tool install git+https://github.com/kmlawson/lmsp.git

# Or clone and install locally
git clone https://github.com/kmlawson/lmsp.git
cd lmsp
uv tool install .
```

#### Install in virtual environment
```bash
# Using uv
uv venv
source .venv/bin/activate
uv pip install lmsp

# Or using pip
python -m venv venv
source venv/bin/activate
pip install lmsp
```

#### Development installation
```bash
# Clone and install in development mode
git clone https://github.com/kmlawson/lmsp.git
cd lmsp
uv pip install -e .  # or pip install -e .
```

## Configuration

lmsp supports a configuration file to set default values for command-line options. The configuration file is located at `~/.lmsp-config` and is automatically created with default values when you first run lmsp.

### Configuration File Format

The configuration file uses JSON format:

```json
{
  "model": null,
  "port": 1234,
  "pipe_mode": "replace",
  "wait": false,
  "stats": false,
  "plain": false,
  "verbose": false
}
```

### Configuration Options

- **model**: Default model to use (null means use first loaded model)
- **port**: Default LM Studio server port (1234)
- **pipe_mode**: How to handle piped input ("replace", "append", or "prepend")
- **wait**: Disable streaming by default (false)
- **stats**: Show response statistics by default (false)
- **plain**: Disable markdown formatting by default (false)
- **verbose**: Enable verbose logging by default (false)

### Example Custom Configuration

```json
{
  "model": "google/gemma-3n-e4b",
  "port": 1234,
  "pipe_mode": "append",
  "wait": true,
  "stats": true,
  "plain": false,
  "verbose": false
}
```

This configuration would:
- Use "google/gemma-3n-e4b" as the default model
- Wait for complete responses (no streaming) and beautify markdown output
- Show response statistics by default
- Append piped content to prompts

Command-line arguments always override configuration file settings.

## Usage

### Prerequisites
Before using lmsp, you need to load a model:
```bash
# Load a model using lms command
lms load google/gemma-3n-e4b

# Or use LM Studio desktop app to load a model
```

### Basic usage
```bash
lmsp "What is the capital of France?"
```

### Specify a model
```bash
# Use a specific model (must be already loaded)
lmsp -m llama-3.2-1b-instruct "Explain quantum computing"

# Enable verbose logging for debugging
lmsp -v -m google/gemma-3n-e4b "What is AI?"
```

### Pipe input
```bash
# Simple piping - replaces the prompt
cat document.txt | lmsp

# Combine prompt with piped content (default appends)
cat document.txt | lmsp "Summarize this document:"

# Control how piped input is combined
cat context.txt | lmsp "Answer based on context:" --pipe-mode prepend
cat document.txt | lmsp "Summarize:" --pipe-mode append

# Real example: Translate a text to English
cat tests/testdata/test-text.md | lmsp "Please translate the following text to English:"
```

### Check loaded models
```bash
# List currently loaded models
lmsp --list-models

# List all available models (not loaded)
lms ls
```

### Check server status
```bash
lmsp --check-server
```

### Get help
```bash
lmsp --help
# or lmsp -h
```

## Security Considerations

When using `lmsp`, please be aware of the following security considerations:

### Piped Content
- **Be cautious about what content you pipe to `lmsp`**. The piped content is directly appended or prepended to your prompt without sanitization.
- Avoid piping untrusted content or files from unknown sources
- Be especially careful when piping content that might contain prompt injection attempts or malicious instructions
- Example of what to avoid:
  ```bash
  # Don't pipe untrusted user input or files
  cat untrusted_user_file.txt | lmsp "Summarize this:"
  ```

### Model Selection
- Only use trusted models that you have intentionally loaded into LM Studio
- Be aware that models will execute the prompts you send, including any piped content

### Local Usage
- `lmsp` is designed for local use with your own LM Studio instance
- It connects to `localhost` only and does not expose any network services

## Prerequisites

1. LM Studio must be installed
2. The LM Studio server must be running (`lms server start`)
3. At least one model must be loaded (`lms load <model>`)

## Running Tests

```bash
python -m unittest tests.test_lmsp -v
```

## Planned Features

- Ability to attach images with `-a` flag for multi-modal models
- Ability to continue from last prompt
- Enhanced piping support for documents
