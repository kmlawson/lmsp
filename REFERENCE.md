# LM Studio CLI (lms) Reference

## Overview
The `lms` command is the official CLI tool for LM Studio that allows you to manage and interact with local language models from the command line.

## Installation
- Automatically ships with LM Studio
- Located in `~/.lmstudio/bin/`
- Must run LM Studio once before using lms
- Bootstrap using platform-specific commands

## Core Commands

### Server Management
- `lms server start` - Launch the local API server
  - `--port <number>` - Specify custom port (default: last used port)
  - `--cors` - Enable CORS support (use with caution)
- `lms server stop` - Shut down the local server
- `lms server status` - Check server status

### Model Management
- `lms ls` - List all downloaded models
- `lms ps` - List currently loaded models
- `lms load <model>` - Load a model
  - Supports optional GPU and context length settings
- `lms unload <model>` - Unload a model
- `lms get` - Search and download models from online

### Interactive Features
- `lms chat` - Open an interactive chat with the currently loaded model
- `lms log stream` - Stream logs from LM Studio (useful for debugging)

### Development Commands
- `lms create` - Create a new project with scaffolding
- `lms dev` - Start development server for plugin in current folder
- `lms push` - Upload plugin to LM Studio Hub
- `lms clone` - Clone artifact from LM Studio Hub

### Other Commands
- `lms status` - Print LM Studio status
- `lms import` - Import a model file into LM Studio
- `lms flags` - Set or get experiment flags
- `lms login` - Authenticate with LM Studio
- `lms bootstrap` - Bootstrap the CLI
- `lms version` - Print CLI version

## API Server Details
When the server is started using `lms server start`, it provides an HTTP API endpoint for interacting with loaded models. This allows programmatic access to the models for tasks like text generation.

## Important Notes
- Models must be loaded before they can be used
- The server must be running to interact with models via API
- Use `lms <subcommand> --help` for detailed help on any command
- When using CORS, be aware of potential security risks

## Python SDK
The LM Studio Python SDK provides programmatic access to models:

### Installation
```bash
pip install lmstudio
```

### Key Features
- Chat and text completions with local language models
- Create autonomous agents using function tools
- Load, configure, and unload models
- Generate text embeddings

### Quick Example
```python
import lmstudio as lms

model = lms.llm("llama-3.2-1b-instruct")
result = model.respond("What is the meaning of life?")
print(result)
```

### Usage Approaches
1. **Interactive Convenience API**: Quick access with default client instance
2. **Scoped Resource API**: Context managers for deterministic resource management

### Additional Notes
- Models can be downloaded via CLI: `lms get <model-name>`
- Source code available on GitHub
- Supports local model interactions and AI agent development

## License
MIT Licensed