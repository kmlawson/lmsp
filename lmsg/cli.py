#!/usr/bin/env python3
import argparse
import sys
import subprocess
import json
import requests
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

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

def get_loaded_models() -> List[dict]:
    """Get list of loaded models using lms ps command"""
    try:
        logger.debug("Getting loaded models with 'lms ps --json'")
        result = subprocess.run(['lms', 'ps', '--json'], capture_output=True, text=True)
        logger.debug(f"lms ps returned code {result.returncode}, stdout: {result.stdout[:200]}")
        
        if result.returncode == 0 and result.stdout:
            models = json.loads(result.stdout)
            logger.info(f"Found {len(models)} loaded models")
            return models
        else:
            # Fallback to parsing non-JSON output
            logger.debug("Falling back to non-JSON parsing")
            result = subprocess.run(['lms', 'ps'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header if present
                    # Simple parsing - just get first model identifier
                    for line in lines[1:]:
                        if line.strip():
                            model = {"identifier": line.split()[0]}
                            logger.info(f"Found model: {model['identifier']}")
                            return [model]
            logger.warning("No models found")
            return []
    except Exception as e:
        logger.error(f"Error getting loaded models: {e}")
        return []

def get_server_status() -> Optional[dict]:
    """Check if LM Studio server is running"""
    try:
        logger.debug("Checking server status with 'lms server status --json'")
        result = subprocess.run(['lms', 'server', 'status', '--json'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            status = json.loads(result.stdout)
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
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return {"running": False}

def list_available_models() -> List[str]:
    """List all available models that can be loaded"""
    try:
        logger.debug("Listing available models with 'lms ls'")
        result = subprocess.run(['lms', 'ls'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            models = result.stdout.strip().split('\n')
            models = [m.strip() for m in models if m.strip()]
            logger.info(f"Found {len(models)} available models")
            return models
        logger.warning("No available models found")
        return []
    except Exception as e:
        logger.error(f"Error listing available models: {e}")
        return []

def ensure_model_loaded(model_name: str) -> bool:
    """Ensure a model is loaded, loading it if necessary"""
    logger.debug(f"Ensuring model '{model_name}' is loaded")
    
    # Check if model is already loaded
    loaded_models = get_loaded_models()
    for loaded in loaded_models:
        if loaded.get("identifier") == model_name or loaded.get("name") == model_name:
            logger.info(f"Model '{model_name}' is already loaded")
            return True
    
    # Try to load the model
    logger.info(f"Model '{model_name}' not loaded, attempting to load...")
    try:
        result = subprocess.run(['lms', 'load', model_name], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Successfully loaded model '{model_name}'")
            return True
        else:
            logger.error(f"Failed to load model: {result.stderr}")
            
            # If model doesn't exist, list available models
            if "not found" in result.stderr.lower() or "does not exist" in result.stderr.lower():
                logger.info("Listing available models...")
                available = list_available_models()
                if available:
                    print("\nAvailable models:", file=sys.stderr)
                    for model in available:
                        print(f"  - {model}", file=sys.stderr)
                    print(f"\nUse 'lms load <model>' to load one of these models", file=sys.stderr)
            return False
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return False

def send_prompt(prompt: str, model: Optional[str] = None, port: int = 1234) -> str:
    """Send a prompt to the LM Studio server"""
    url = f"http://localhost:{port}/v1/chat/completions"
    logger.debug(f"Sending prompt to {url} with model: {model}")
    
    # If no model specified, use the first loaded model
    if not model:
        models = get_loaded_models()
        if not models:
            return "Error: No models loaded. Use 'lms load <model>' to load a model."
        model = models[0].get("identifier", models[0].get("name", ""))
        logger.info(f"Using default model: {model}")
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": -1,
        "stream": False
    }
    
    logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        logger.debug(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Response data: {json.dumps(data, indent=2)[:500]}")
            return data['choices'][0]['message']['content']
        else:
            error_msg = f"Error: Server returned status {response.status_code}: {response.text}"
            logger.error(error_msg)
            return error_msg
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return "Error: Could not connect to LM Studio server. Make sure it's running with 'lms server start'"
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error: {e}")
        return "Error: Request timed out"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Error: {str(e)}"

def main():
    parser = argparse.ArgumentParser(
        description='Send prompts to LM Studio loaded models',
        prog='lmsg'
    )
    
    parser.add_argument('prompt', 
                       nargs='?',
                       help='The prompt to send to the model')
    
    parser.add_argument('-m', '--model',
                       help='Specify which model to use (default: first loaded model)')
    
    parser.add_argument('-p', '--port',
                       type=int,
                       default=1234,
                       help='LM Studio server port (default: 1234)')
    
    parser.add_argument('--pipe-mode',
                       choices=['replace', 'append', 'prepend'],
                       default='replace',
                       help='How to handle piped input: replace (default), append, or prepend to prompt')
    
    parser.add_argument('--list-models',
                       action='store_true',
                       help='List currently loaded models')
    
    parser.add_argument('--check-server',
                       action='store_true',
                       help='Check if LM Studio server is running')
    
    parser.add_argument('-v', '--verbose',
                       action='store_true',
                       help='Enable verbose logging for debugging')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Handle special commands
    if args.list_models:
        models = get_loaded_models()
        if models:
            print("Loaded models:")
            for model in models:
                print(f"  - {model.get('identifier', model.get('name', 'Unknown'))}")
        else:
            print("No models currently loaded")
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
    
    # If model specified, ensure it's loaded
    if args.model:
        logger.info(f"Ensuring model '{args.model}' is loaded...")
        if not ensure_model_loaded(args.model):
            print(f"Error: Failed to load model '{args.model}'", file=sys.stderr)
            sys.exit(1)
    
    # Send the prompt
    response = send_prompt(final_prompt, args.model, args.port)
    print(response)

if __name__ == "__main__":
    main()