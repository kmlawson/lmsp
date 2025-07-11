# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.5] - 2025-01-11

### Changed
- Changed default `pipe_mode` from "replace" to "append" in configuration
- Added `claude.md` and `CLAUDE.md` to `.gitignore`

## [0.5.0] - 2025-01-11

### Added
- Configuration file support (`~/.lmsp-config`) with auto-creation
- JSON configuration validation and error handling
- Config file location displayed in help text
- Support for configurable defaults for all command-line options

### Changed
- Removed auto-loading functionality - models must be pre-loaded using `lms load <model>` or LM Studio desktop
- Updated error messages to guide users to load models manually
- Enhanced help text to clarify model loading requirements
- Updated README to emphasize PyPI installation method
- Updated LICENSE copyright to "Konrad M. Lawson 2025"

### Fixed
- Fixed test failures by properly mocking configuration loading
- Improved error handling for missing models

## [0.1.0] - 2025-01-11

### Added
- Initial release of lmsp CLI tool
- Send prompts to LM Studio loaded models
- Support for streaming and non-streaming responses
- Pipe mode support (replace, append, prepend)
- Markdown formatting with terminal colors
- Response statistics (token count, latency, tokens per second)
- Model validation and security features
- Comprehensive test suite
- Command-line options for port, model selection, and output formatting
- Integration with LM Studio's `lms` command-line tool

### Security
- Input validation for model names, ports, and prompts
- Terminal output sanitization to prevent injection attacks
- JSON bomb protection with size and depth limits
- Memory exhaustion protection
- ANSI escape sequence filtering