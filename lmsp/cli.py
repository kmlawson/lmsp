#!/usr/bin/env python3
import argparse
import sys
import subprocess
import json
import requests
import logging
import time
import re
import shlex
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Configuration constants
MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB max JSON
MAX_JSON_DEPTH = 20  # Maximum nesting depth for JSON objects
MAX_OUTPUT_TOKENS = 100000  # Max tokens to prevent memory exhaustion
MAX_TOKEN_BYTES = 1024 * 1024  # 1MB max per individual token to prevent memory exhaustion
MIN_PORT = 1024
MAX_PORT = 65535
REQUEST_TIMEOUT = 60

# Configuration file
CONFIG_FILE = Path.home() / ".lmsp-config"

# Security: Whitelist pattern for model names (allow slashes for namespaced models)
MODEL_NAME_PATTERN = re.compile(r'^[A-Za-z0-9._\-/]+$')

class LMSPSecurityError(Exception):
    """Custom exception for security-related errors"""
    pass

class LMSPValidationError(Exception):
    """Custom exception for validation errors"""
    pass

def validate_model_name(model_name: str) -> str:
    """Validate model name against security whitelist"""
    if model_name is None:
        raise LMSPValidationError("Model name cannot be None")
        
    if not isinstance(model_name, str):
        raise LMSPValidationError("Model name must be a string")
    
    # Security: Check for whitespace/control characters BEFORE stripping
    if any(c.isspace() for c in model_name):
        raise LMSPValidationError("Model name cannot contain whitespace characters")
    
    # Check for control characters and non-printable characters
    if any(ord(c) < 32 or ord(c) == 127 or ord(c) > 126 for c in model_name):
        raise LMSPValidationError("Model name contains invalid control or non-ASCII characters")
    
    if not model_name:
        raise LMSPValidationError("Model name cannot be empty")
    
    if len(model_name) > 100:
        raise LMSPValidationError("Model name too long (max 100 characters)")
    
    if not MODEL_NAME_PATTERN.match(model_name):
        raise LMSPValidationError(
            "Model name contains invalid characters. Only alphanumeric, dots, hyphens, underscores and slashes allowed."
        )
    
    # Security: Prevent directory traversal attacks
    if '..' in model_name or model_name.startswith('/') or model_name.endswith('/'):
        raise LMSPValidationError("Model name cannot contain directory traversal patterns")
    
    return model_name

def validate_port(port: int) -> int:
    """Validate port number to prevent SSRF"""
    if not isinstance(port, int):
        raise LMSPValidationError("Port must be an integer")
    
    if port < MIN_PORT or port > MAX_PORT:
        raise LMSPValidationError(f"Port must be between {MIN_PORT} and {MAX_PORT}")
    
    return port

def validate_prompt(prompt: str) -> str:
    """Validate prompt content"""
    if not prompt:
        raise LMSPValidationError("Prompt cannot be empty")
    
    return prompt

def sanitize_terminal_output(text: str) -> str:
    """Remove ANSI escape sequences to prevent terminal injection"""
    # Remove ANSI escape sequences except for our own formatting
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def safe_json_loads(json_str: str) -> Any:
    """Safely parse JSON with size and depth limits to prevent JSON bomb attacks"""
    # Security: Check raw size first
    if len(json_str.encode('utf-8')) > MAX_JSON_SIZE:
        raise LMSPSecurityError(f"JSON response too large ({len(json_str)} bytes > {MAX_JSON_SIZE})")
    
    # Security: Parse with depth checking
    class DepthCheckingDecoder(json.JSONDecoder):
        def __init__(self, max_depth=MAX_JSON_DEPTH):
            super().__init__()
            self.max_depth = max_depth
            self.current_depth = 0
        
        def decode(self, s):
            self.current_depth = 0
            return self._decode_with_depth_check(super().decode(s))
        
        def _decode_with_depth_check(self, obj, depth=0):
            if depth > self.max_depth:
                raise LMSPSecurityError(f"JSON nesting too deep (depth {depth} > {self.max_depth})")
            
            if isinstance(obj, dict):
                return {k: self._decode_with_depth_check(v, depth + 1) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [self._decode_with_depth_check(item, depth + 1) for item in obj]
            else:
                return obj
    
    try:
        return json.loads(json_str, cls=DepthCheckingDecoder)
    except json.JSONDecodeError as e:
        # Re-raise as our own exception for consistent handling
        raise json.JSONDecodeError(str(e), e.doc, e.pos)

def format_markdown(text: str, plain: bool = False) -> str:
    """Format markdown text with terminal colors/styles"""
    # Security: Limit input size to prevent ReDoS attacks
    if len(text) > 50000:  # 50KB limit for formatting
        text = text[:50000] + "...[truncated]"
    
    if plain:
        # Remove markdown formatting for plain text output - use character classes to prevent ReDoS
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'\1', text)  # Italic - no newlines
        text = re.sub(r'`([^`\n]+)`', r'\1', text)        # Code - no newlines
        text = re.sub(r'^#{1,6}\s*(.*)$', r'\1', text, flags=re.MULTILINE)  # Headers
        return text
    
    # Terminal color codes
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    
    # Headers (# ## ###) - limit line length to prevent ReDoS
    text = re.sub(r'^(#{1,3})\s*(.{0,200})$', f'{CYAN}{BOLD}\\2{RESET}', text, flags=re.MULTILINE)
    text = re.sub(r'^(#{4,6})\s*(.{0,200})$', f'{CYAN}\\2{RESET}', text, flags=re.MULTILINE)
    
    # Bold text (**text**) - prevent ReDoS with length limits
    text = re.sub(r'\*\*([^*]{1,200})\*\*', f'{BOLD}\\1{RESET}', text)
    
    # Italic text (*text*) - prevent ReDoS with length limits and no newlines
    text = re.sub(r'(?<!\*)\*([^*\n]{1,200})\*(?!\*)', f'{DIM}\\1{RESET}', text)
    
    # Inline code (`code`) - prevent ReDoS with length limits
    text = re.sub(r'`([^`\n]{1,200})`', f'{BLUE}\\1{RESET}', text)
    
    return text

def setup_logging(verbose: bool = False):
    """Set up logging configuration"""
    level = logging.DEBUG if verbose else logging.WARNING
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s' if verbose else '%(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        stream=sys.stderr
    )
    logger.setLevel(level)

def get_default_config() -> Dict[str, Any]:
    """Get default configuration values"""
    return {
        "model": None,
        "port": 1234,
        "pipe_mode": "replace",
        "wait": False,
        "stats": False,
        "plain": False,
        "verbose": False
    }

def load_config() -> Dict[str, Any]:
    """Load configuration from file, creating it if it doesn't exist"""
    config = get_default_config()
    
    try:
        if CONFIG_FILE.exists():
            logger.debug(f"Loading config from {CONFIG_FILE}")
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = safe_json_loads(f.read())
                
                # Validate and merge config values
                if isinstance(file_config, dict):
                    for key, value in file_config.items():
                        if key in config:
                            # Validate specific config values
                            if key == "port" and isinstance(value, int):
                                try:
                                    config[key] = validate_port(value)
                                except LMSPValidationError:
                                    logger.warning(f"Invalid port in config: {value}, using default")
                            elif key == "model":
                                if value is not None:
                                    try:
                                        config[key] = validate_model_name(str(value))
                                    except LMSPValidationError:
                                        logger.warning(f"Invalid model name in config: {value}, using default")
                                else:
                                    config[key] = None
                            elif key == "pipe_mode" and value in ["replace", "append", "prepend"]:
                                config[key] = value
                            elif key in ["wait", "stats", "plain", "verbose"] and isinstance(value, bool):
                                config[key] = value
                            else:
                                logger.warning(f"Invalid config value for {key}: {value}, using default")
                        else:
                            logger.warning(f"Unknown config key: {key}")
                else:
                    logger.warning("Config file is not a valid JSON object, using defaults")
        else:
            logger.debug(f"Config file {CONFIG_FILE} does not exist, creating with defaults")
            save_config(config)
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}, using defaults")
    except LMSPSecurityError as e:
        logger.error(f"Security error in config file: {e}, using defaults")
    except Exception as e:
        logger.error(f"Error loading config: {e}, using defaults")
    
    return config

def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file"""
    try:
        logger.debug(f"Saving config to {CONFIG_FILE}")
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

def get_loaded_models() -> List[dict]:
    """Get list of loaded models using lms ps command"""
    try:
        logger.debug("Getting loaded models with 'lms ps --json'")
        # Security: Use list form to prevent command injection
        result = subprocess.run(['lms', 'ps', '--json'], capture_output=True, text=True, shell=False, timeout=30)
        logger.debug(f"lms ps returned code {result.returncode}, stdout: {result.stdout[:200]}")
        
        if result.returncode == 0 and result.stdout:
            # Security: Parse JSON safely with size and depth limits
            models = safe_json_loads(result.stdout)
            logger.info(f"Found {len(models)} loaded models")
            return models
        else:
            # Fallback to parsing non-JSON output
            logger.debug("Falling back to non-JSON parsing")
            result = subprocess.run(['lms', 'ps'], capture_output=True, text=True, shell=False, timeout=30)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header if present
                    # Security: Validate parsed model names from plaintext
                    for line in lines[1:]:
                        if line.strip():
                            parts = line.split()
                            if parts:
                                raw_model_name = parts[0]
                                try:
                                    # Security: Apply same validation as JSON parsing
                                    validated_name = validate_model_name(raw_model_name)
                                    model = {"identifier": validated_name}
                                    logger.info(f"Found model: {model['identifier']}")
                                    return [model]
                                except LMSPValidationError as e:
                                    logger.warning(f"Skipping invalid model name '{raw_model_name}': {e}")
                                    continue
            logger.warning("No models found")
            return []
    except subprocess.TimeoutExpired:
        logger.error("Timeout getting loaded models")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {e}")
        return []
    except LMSPSecurityError as e:
        logger.error(f"Security error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting loaded models: {e}")
        return []

def get_server_status() -> Optional[dict]:
    """Check if LM Studio server is running"""
    try:
        logger.debug("Checking server status with 'lms server status --json'")
        # Security: Use list form to prevent command injection
        result = subprocess.run(['lms', 'server', 'status', '--json'], capture_output=True, text=True, shell=False, timeout=30)
        if result.returncode == 0 and result.stdout:
            # Security: Parse JSON safely with size and depth limits
            status = safe_json_loads(result.stdout)
            logger.info(f"Server status: {status}")
            return status
        else:
            # Fallback - check if server responds
            logger.debug("Falling back to HTTP check")
            try:
                response = requests.get('http://localhost:1234/v1/models', timeout=2)
                if response.status_code == 200:
                    logger.info("Server is running on port 1234")
                    return {"running": True, "port": 1234}
            except Exception as e:
                logger.debug(f"HTTP check failed: {e}")
            logger.warning("Server is not running")
            return {"running": False}
    except subprocess.TimeoutExpired:
        logger.error("Timeout checking server status")
        return {"running": False}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {e}")
        return {"running": False}
    except LMSPSecurityError as e:
        logger.error(f"Security error: {e}")
        return {"running": False}
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return {"running": False}

def list_available_models() -> List[str]:
    """List all available models that can be loaded"""
    try:
        logger.debug("Listing available models with 'lms ls'")
        # Security: Use list form to prevent command injection
        result = subprocess.run(['lms', 'ls'], capture_output=True, text=True, shell=False, timeout=30)
        if result.returncode == 0 and result.stdout:
            models = result.stdout.strip().split('\n')
            validated_models = []
            for model in models:
                model = model.strip()
                if model:
                    try:
                        # Security: Validate all model names from external source
                        validated_model = validate_model_name(model)
                        validated_models.append(validated_model)
                    except LMSPValidationError as e:
                        logger.warning(f"Skipping invalid model name '{model}': {e}")
                        continue
            logger.info(f"Found {len(validated_models)} available models")
            return validated_models
        logger.warning("No available models found")
        return []
    except subprocess.TimeoutExpired:
        logger.error("Timeout listing available models")
        return []
    except Exception as e:
        logger.error(f"Error listing available models: {e}")
        return []

def check_model_loaded(model_name: str) -> bool:
    """Check if a specific model is loaded"""
    try:
        # Security: Validate model name to prevent command injection
        validated_model_name = validate_model_name(model_name)
        logger.debug(f"Checking if model '{validated_model_name}' is loaded")
        
        # Check if model is loaded
        loaded_models = get_loaded_models()
        for loaded in loaded_models:
            if loaded.get("identifier") == validated_model_name or loaded.get("name") == validated_model_name:
                logger.info(f"Model '{validated_model_name}' is loaded")
                return True
        
        logger.info(f"Model '{validated_model_name}' is not loaded")
        return False
    except LMSPValidationError as e:
        logger.error(f"Invalid model name '{model_name}': {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking model: {e}")
        return False

def send_prompt(prompt: str, model: Optional[str] = None, port: int = 1234, stream: bool = True, show_stats: bool = False, plain: bool = False) -> tuple[str, Optional[Dict[str, Any]]]:
    """Send a prompt to the LM Studio server"""
    try:
        # Security: Validate inputs
        validated_prompt = validate_prompt(prompt)
        validated_port = validate_port(port)
        
        if model:
            validated_model = validate_model_name(model)
        else:
            validated_model = None
        
        url = f"http://localhost:{validated_port}/v1/chat/completions"
        logger.debug(f"Sending prompt to {url} with model: {validated_model}")
        
        # If no model specified, use the first loaded model
        if not validated_model:
            models = get_loaded_models()
            if not models:
                available_models = list_available_models()
                if available_models:
                    error_msg = "Error: No models loaded. Load a model first using 'lms load <model>' or LM Studio desktop app.\n\nAvailable models:"
                    for model in available_models[:5]:  # Show first 5 models
                        error_msg += f"\n  - {model}"
                    if len(available_models) > 5:
                        error_msg += f"\n  ... and {len(available_models) - 5} more"
                    error_msg += f"\n\nUse 'lms load <model>' to load a model."
                else:
                    error_msg = "Error: No models loaded and no available models found. Please install models in LM Studio first."
                return error_msg, None
            
            # Security: Validate default model name from external source
            raw_model_name = models[0].get("identifier", models[0].get("name", ""))
            if not raw_model_name:
                return "Error: Invalid model data from server (no identifier or name).", None
            
            try:
                validated_model = validate_model_name(raw_model_name)
                logger.info(f"Using default model: {validated_model}")
            except LMSPValidationError as e:
                logger.error(f"Default model name validation failed: {e}")
                return "Error: Default model name is invalid. Please specify a valid model with -m option.", None
        
        payload = {
            "model": validated_model,
            "messages": [
                {"role": "user", "content": validated_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": -1,
            "stream": stream
        }
    except LMSPValidationError as e:
        logger.error(f"Validation error: {e}")
        return f"Error: {str(e)}", None
    
    logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
    
    stats = None
    start_time = time.time()
    first_token_time = None
    token_count = 0
    json_bytes_accumulated = 0  # Track JSON size across streaming session
    
    try:
        if stream:
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=60)
            response.encoding = 'utf-8'
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                content = ""
                consecutive_newlines = 0
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                # Security: Track accumulated JSON size to prevent JSON bomb via streaming
                                json_bytes_accumulated += len(data_str.encode('utf-8'))
                                if json_bytes_accumulated > MAX_JSON_SIZE:
                                    logger.warning(f"Accumulated JSON size too large ({json_bytes_accumulated} bytes), stopping")
                                    break
                                
                                chunk_data = safe_json_loads(data_str)
                                delta = chunk_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    token = delta['content']
                                    if first_token_time is None:
                                        first_token_time = time.time()
                                    
                                    # Security: Check individual token byte size to prevent memory exhaustion
                                    token_bytes = len(token.encode('utf-8'))
                                    if token_bytes > MAX_TOKEN_BYTES:
                                        logger.warning(f"Token too large ({token_bytes} bytes), truncating")
                                        token = token[:MAX_TOKEN_BYTES//4] + "...[truncated]"
                                    
                                    content += token
                                    token_count += 1
                                    
                                    # Security: ALWAYS sanitize output to prevent terminal injection
                                    safe_token = sanitize_terminal_output(token)
                                    
                                    # Handle blank line limiting during streaming
                                    if '\n' in safe_token:
                                        # Count newlines in this token
                                        newline_count = safe_token.count('\n')
                                        
                                        # Split token into parts around newlines
                                        if safe_token == '\n' or safe_token == '\n\n':
                                            consecutive_newlines += newline_count
                                            # Only allow up to 2 consecutive newlines (1 blank line)
                                            if consecutive_newlines <= 2:
                                                print(safe_token, end='', flush=True)
                                        else:
                                            # Token contains content + newlines, reset counter and print
                                            consecutive_newlines = newline_count
                                            print(safe_token, end='', flush=True)
                                    else:
                                        consecutive_newlines = 0
                                        print(safe_token, end='', flush=True)
                                    
                                    # Force immediate output
                                    sys.stdout.flush()
                                    
                                    # Security: Prevent memory exhaustion
                                    if token_count > MAX_OUTPUT_TOKENS:
                                        logger.warning(f"Output truncated at {MAX_OUTPUT_TOKENS} tokens")
                                        break
                            except json.JSONDecodeError:
                                continue
                # Don't add extra newline - streaming already handled it
                
                end_time = time.time()
                if show_stats and first_token_time:
                    stats = {
                        'first_token_latency': first_token_time - start_time,
                        'total_latency': end_time - start_time,
                        'token_count': token_count,
                        'tokens_per_second': token_count / (end_time - first_token_time) if end_time > first_token_time else 0
                    }
                
                # Clean up content for return value (remove excessive newlines at end)
                clean_content = content.rstrip('\n')
                return clean_content, stats
            else:
                # Security: Sanitize server error output to prevent ANSI injection
                safe_error_text = sanitize_terminal_output(response.text)
                error_msg = f"Error: Server returned status {response.status_code}: {safe_error_text}"
                logger.error(error_msg)
                return error_msg, None
        else:
            # For non-streaming mode, we'll actually use streaming internally but show progress
            payload['stream'] = True  # Use streaming for progress indication
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=60)
            response.encoding = 'utf-8'
            logger.debug(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                content = ""
                token_count = 0
                json_bytes_accumulated = 0  # Reset for non-streaming path
                progress_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
                progress_idx = 0
                
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                # Security: Track accumulated JSON size to prevent JSON bomb via streaming
                                json_bytes_accumulated += len(data_str.encode('utf-8'))
                                if json_bytes_accumulated > MAX_JSON_SIZE:
                                    logger.warning(f"Accumulated JSON size too large ({json_bytes_accumulated} bytes), stopping")
                                    break
                                
                                chunk_data = safe_json_loads(data_str)
                                delta = chunk_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    token = delta['content']
                                    if first_token_time is None:
                                        first_token_time = time.time()
                                    
                                    # Security: Check individual token byte size to prevent memory exhaustion
                                    token_bytes = len(token.encode('utf-8'))
                                    if token_bytes > MAX_TOKEN_BYTES:
                                        logger.warning(f"Token too large ({token_bytes} bytes), truncating")
                                        token = token[:MAX_TOKEN_BYTES//4] + "...[truncated]"
                                    
                                    content += token
                                    token_count += 1
                                    
                                    # Show progress indicator (only every 5 tokens to reduce flicker)
                                    if token_count % 5 == 0:
                                        progress_char = progress_chars[progress_idx % len(progress_chars)]
                                        print(f"\r{progress_char} Generating response... ({token_count} tokens)", end='', flush=True)
                                        progress_idx += 1
                                    
                                    # Security: Prevent memory exhaustion
                                    if token_count > MAX_OUTPUT_TOKENS:
                                        logger.warning(f"Output truncated at {MAX_OUTPUT_TOKENS} tokens")
                                        break
                            except json.JSONDecodeError:
                                continue
                
                # Clear progress line
                print(f"\r{' ' * 50}\r", end='', flush=True)
                
                end_time = time.time()
                if show_stats:
                    stats = {
                        'first_token_latency': first_token_time - start_time if first_token_time else None,
                        'total_latency': end_time - start_time,
                        'token_count': token_count,
                        'tokens_per_second': token_count / (end_time - first_token_time) if first_token_time and end_time > first_token_time else None
                    }
                
                clean_content = content.rstrip('\n')
                # Debug: log the content before formatting
                logger.debug(f"Content before formatting: {repr(clean_content[:500])}")
                return clean_content, stats
            else:
                # Security: Sanitize server error output to prevent ANSI injection
                safe_error_text = sanitize_terminal_output(response.text)
                error_msg = f"Error: Server returned status {response.status_code}: {safe_error_text}"
                logger.error(error_msg)
                return error_msg, None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return "Error: Could not connect to LM Studio server. Make sure it's running with 'lms server start'", None
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error: {e}")
        return "Error: Request timed out", None
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error: {e}")
        return f"Error: HTTP request failed: {str(e)}", None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return "Error: Invalid response from server", None
    except LMSPValidationError as e:
        logger.error(f"Validation error: {e}")
        return f"Error: {str(e)}", None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Error: {str(e)}", None

def main():
    # Load configuration first
    config = load_config()
    
    parser = argparse.ArgumentParser(
        description='Send prompts to LM Studio loaded models. Models must be pre-loaded using "lms load <model>" or LM Studio desktop app.',
        prog='lmsp'
    )
    
    parser.add_argument('prompt', 
                       nargs='?',
                       help='The prompt to send to the model')
    
    parser.add_argument('-m', '--model',
                       default=config.get('model'),
                       help='Specify which model to use (must be already loaded - default: first loaded model)')
    
    def validate_port_arg(value):
        try:
            port = int(value)
            return validate_port(port)
        except (ValueError, LMSPValidationError) as e:
            raise argparse.ArgumentTypeError(f"Invalid port: {e}")
    
    parser.add_argument('--port',
                       type=validate_port_arg,
                       default=config.get('port', 1234),
                       help=f'LM Studio server port (default: {config.get("port", 1234)}, range: {MIN_PORT}-{MAX_PORT})')
    
    parser.add_argument('--pipe-mode',
                       choices=['replace', 'append', 'prepend'],
                       default=config.get('pipe_mode', 'replace'),
                       help=f'How to handle piped input: replace, append, or prepend to prompt (default: {config.get("pipe_mode", "replace")})')
    
    parser.add_argument('--list-models',
                       action='store_true',
                       help='List currently loaded models (use "lms ls" to see all available models)')
    
    parser.add_argument('--check-server',
                       action='store_true',
                       help='Check if LM Studio server is running')
    
    # For boolean flags, we need to handle the config defaults differently
    wait_default = config.get('wait', False)
    parser.add_argument('-w', '--wait',
                       action='store_true',
                       default=wait_default,
                       help=f'Wait for complete response before returning (disable streaming) (default: {wait_default})')
    
    stats_default = config.get('stats', False)
    parser.add_argument('-s', '--stats',
                       action='store_true',
                       default=stats_default,
                       help=f'Show response statistics (first token latency, tokens/sec, total time) (default: {stats_default})')
    
    plain_default = config.get('plain', False)
    parser.add_argument('-p', '--plain',
                       action='store_true',
                       default=plain_default,
                       help=f'Disable markdown formatting (useful for piping or saving to files) (default: {plain_default})')
    
    verbose_default = config.get('verbose', False)
    parser.add_argument('-v', '--verbose',
                       action='store_true',
                       default=verbose_default,
                       help=f'Enable verbose logging for debugging (default: {verbose_default})')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Handle special commands
    if args.list_models:
        loaded_models = get_loaded_models()
        if loaded_models:
            print("Loaded models:")
            for model in loaded_models:
                print(f"  - {model.get('identifier', model.get('name', 'Unknown'))}")
        else:
            print("No models currently loaded")
        
        print("\nTo see all available models, use: lms ls")
        print("To load a model, use: lms load <model>")
        return
    
    if args.check_server:
        status = get_server_status()
        if status.get("running"):
            print(f"LM Studio server is running on port {status.get('port', args.port)}")
        else:
            print("LM Studio server is not running")
        return
    
    # Handle piped input
    piped_content = None
    if not sys.stdin.isatty():
        piped_content = sys.stdin.read().strip()
    
    # Determine final prompt based on pipe mode
    final_prompt = args.prompt
    
    if piped_content:
        if args.pipe_mode == 'replace' and not args.prompt:
            final_prompt = piped_content
        elif args.pipe_mode == 'append' and args.prompt:
            final_prompt = f"{args.prompt}\n\n{piped_content}"
        elif args.pipe_mode == 'prepend' and args.prompt:
            final_prompt = f"{piped_content}\n\n{args.prompt}"
        elif args.prompt:
            # Default behavior when both prompt and piped content exist
            final_prompt = f"{args.prompt}\n\n{piped_content}"
        else:
            final_prompt = piped_content
    
    # If no prompt at all, show help
    if not final_prompt:
        parser.print_help()
        return
    
    # Check server status before sending prompt
    status = get_server_status()
    if not status.get("running"):
        print("Error: LM Studio server is not running. Start it with 'lms server start'", file=sys.stderr)
        sys.exit(1)
    
    # If model specified, check if it's loaded
    if args.model:
        try:
            logger.info(f"Checking if model '{args.model}' is loaded...")
            if not check_model_loaded(args.model):
                available_models = list_available_models()
                if available_models:
                    print(f"Error: Model '{args.model}' is not loaded. Load it first using 'lms load {args.model}' or LM Studio desktop app.\n", file=sys.stderr)
                    print("Available models:", file=sys.stderr)
                    for model in available_models[:5]:  # Show first 5 models
                        print(f"  - {model}", file=sys.stderr)
                    if len(available_models) > 5:
                        print(f"  ... and {len(available_models) - 5} more", file=sys.stderr)
                    print(f"\nUse 'lms load <model>' to load a model.", file=sys.stderr)
                else:
                    print(f"Error: Model '{args.model}' is not loaded and no available models found. Please install models in LM Studio first.", file=sys.stderr)
                sys.exit(1)
        except LMSPValidationError as e:
            print(f"Error: Invalid model name. Model names must contain only alphanumeric characters, dots, hyphens, underscores and slashes.", file=sys.stderr)
            sys.exit(1)
    
    # Send the prompt
    use_streaming = not args.wait
    response, stats = send_prompt(final_prompt, args.model, args.port, stream=use_streaming, show_stats=args.stats, plain=args.plain)
    
    # Print response if not streaming (streaming already printed during generation)
    if not use_streaming:
        # Security: Always sanitize before any output processing
        safe_response = sanitize_terminal_output(response)
        if args.plain:
            print(safe_response)
        else:
            formatted_response = format_markdown(safe_response, plain=False)
            print(formatted_response)
    
    # Print stats if requested
    if args.stats and stats:
        print(f"\n--- Response Statistics ---", file=sys.stderr)
        if stats['first_token_latency'] is not None:
            print(f"First token latency: {stats['first_token_latency']:.1f}s", file=sys.stderr)
        if stats['total_latency'] is not None:
            print(f"Total latency: {stats['total_latency']:.1f}s", file=sys.stderr)
        if stats['token_count'] is not None:
            print(f"Token count: {stats['token_count']}", file=sys.stderr)
        if stats['tokens_per_second'] is not None:
            print(f"Tokens per second: {stats['tokens_per_second']:.1f}", file=sys.stderr)

if __name__ == "__main__":
    main()