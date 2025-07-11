# lmsp - LM Studio Prompt CLI

A simple command-line interface for sending prompts to LM Studio loaded models.

## Features

- Send prompts to locally loaded LM Studio models
- Automatically uses the first loaded model (or specify with `-m`)
- **Automatic model loading**: If a model isn't loaded, lmsp will load it for you
- Support for piping input from other commands
- Verbose logging with `-v` flag for debugging
- Simple and fast command-line interface

## Installation

### Option 1: Install as a global tool (Recommended)
```bash
# Using uv tool (recommended - installs globally)
uv tool install .

# Or install from git repository
uv tool install git+https://github.com/yourusername/lmsp.git
```

### Option 2: Install as a package in virtual environment
```bash
# Using uv
uv venv
source .venv/bin/activate
uv pip install -e .

# Or using pip
pip install -e .
```

### Option 3: Direct usage
1. Make sure LM Studio is installed and running
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Use directly:
   ```bash
   python -m lmsp.cli "Your prompt here"
   ```

## Usage

### Basic usage
```bash
lmsp "What is the capital of France?"
```

### Specify a model
```bash
# Use a specific model (loads it automatically if not already loaded)
lmsp -m llama-3.2-1b-instruct "Explain quantum computing"

# Enable verbose logging for debugging
lmsp -v -m llama-3.2-1b-instruct "What is AI?"
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

# Real example: Translate Norwegian text to English
cat tests/testdata/test-text.md | lmsp "Please translate the following Norwegian text to English:"
```

### Check loaded models
```bash
lmsp --list-models
```

### Check server status
```bash
lmsp --check-server
```

### Get help
```bash
lmsp --help
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

- Ability to attach images with `-a` flag
- Ability to continue from last prompt
- Enhanced piping support for documents