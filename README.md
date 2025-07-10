# lmsg - LM Studio Message CLI

A simple command-line interface for sending prompts to LM Studio loaded models.

## Features

- Send prompts to locally loaded LM Studio models
- Automatically uses the first loaded model (or specify with `-m`)
- **Automatic model loading**: If a model isn't loaded, lmsg will load it for you
- Support for piping input from other commands
- Verbose logging with `-v` flag for debugging
- Simple and fast command-line interface

## Installation

### Option 1: Install as a package (Recommended)
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e .

# Or using pip
pip install -e .
```

### Option 2: Direct usage
1. Make sure LM Studio is installed and running
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Use directly:
   ```bash
   python -m lmsg.cli "Your prompt here"
   ```

## Usage

### Basic usage
```bash
lmsg "What is the capital of France?"
```

### Specify a model
```bash
# Use a specific model (loads it automatically if not already loaded)
lmsg -m llama-3.2-1b-instruct "Explain quantum computing"

# Enable verbose logging for debugging
lmsg -v -m llama-3.2-1b-instruct "What is AI?"
```

### Pipe input
```bash
# Simple piping - replaces the prompt
cat document.txt | lmsg

# Combine prompt with piped content (default appends)
cat document.txt | lmsg "Summarize this document:"

# Control how piped input is combined
cat context.txt | lmsg "Answer based on context:" --pipe-mode prepend
cat document.txt | lmsg "Summarize:" --pipe-mode append

# Real example: Translate Norwegian text to English
cat tests/testdata/test-text.md | lmsg "Please translate the following Norwegian text to English:"
```

### Check loaded models
```bash
lmsg --list-models
```

### Check server status
```bash
lmsg --check-server
```

### Get help
```bash
lmsg --help
```

## Prerequisites

1. LM Studio must be installed
2. The LM Studio server must be running (`lms server start`)
3. At least one model must be loaded (`lms load <model>`)

## Running Tests

```bash
python -m unittest tests.test_lmsg -v
```

## Planned Features

- Ability to attach images with `-a` flag
- Ability to continue from last prompt
- Enhanced piping support for documents