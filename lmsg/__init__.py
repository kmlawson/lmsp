"""lmsg - LM Studio Message CLI

A command-line interface for sending prompts to LM Studio loaded models.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .cli import (
    main, 
    send_prompt, 
    get_loaded_models, 
    ensure_model_loaded,
    get_server_status,
    list_available_models,
    setup_logging
)

__all__ = [
    "main", 
    "send_prompt", 
    "get_loaded_models", 
    "ensure_model_loaded",
    "get_server_status",
    "list_available_models",
    "setup_logging"
]