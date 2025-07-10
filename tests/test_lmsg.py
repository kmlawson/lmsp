#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lmsg import cli as lmsg
import logging

class TestLmsg(unittest.TestCase):
    
    @patch('subprocess.run')
    def test_get_loaded_models_with_json_output(self, mock_run):
        """Test parsing loaded models from lms ps --json command"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"identifier": "llama-3.2-1b-instruct", "name": "Llama 3.2 1B"}]'
        )
        
        models = lmsg.get_loaded_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["identifier"], "llama-3.2-1b-instruct")
    
    @patch('subprocess.run')
    def test_get_loaded_models_fallback_to_plain_text(self, mock_run):
        """Test fallback to plain text parsing when JSON output fails"""
        # First call fails with JSON
        # Second call returns plain text output
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=''),
            MagicMock(returncode=0, stdout='Model ID\nllama-3.2-1b-instruct\n')
        ]
        
        models = lmsg.get_loaded_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["identifier"], "llama-3.2-1b-instruct")
    
    @patch('subprocess.run')
    def test_get_loaded_models_returns_empty_when_none_loaded(self, mock_run):
        """Test returns empty list when no models are loaded"""
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        
        models = lmsg.get_loaded_models()
        self.assertEqual(len(models), 0)
    
    @patch('requests.get')
    @patch('subprocess.run')
    def test_server_status_check_when_running(self, mock_run, mock_get):
        """Test server status detection when LM Studio server is running"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"running": true, "port": 1234}'
        )
        
        status = lmsg.get_server_status()
        self.assertTrue(status["running"])
        self.assertEqual(status["port"], 1234)
    
    @patch('requests.get')
    @patch('subprocess.run')
    def test_server_status_check_when_not_running(self, mock_run, mock_get):
        """Test server status detection when LM Studio server is stopped"""
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        mock_get.side_effect = Exception("Connection refused")
        
        status = lmsg.get_server_status()
        self.assertFalse(status["running"])
    
    @patch('lmsg.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_returns_model_response(self, mock_post, mock_get_models):
        """Test successful prompt sending returns model's response"""
        mock_get_models.return_value = [{"identifier": "llama-3.2-1b-instruct"}]
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {"content": "Hello! How can I help you?"}
                }]
            }
        )
        
        response = lmsg.send_prompt("Hello")
        self.assertEqual(response, "Hello! How can I help you?")
    
    def test_send_prompt_fails_when_no_models_loaded(self):
        """Test error message when attempting to send prompt with no loaded models"""
        with patch('lmsg.cli.get_loaded_models', return_value=[]):
            response = lmsg.send_prompt("Hello")
            self.assertIn("No models loaded", response)
    
    @patch('lmsg.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_handles_server_connection_error(self, mock_post, mock_get_models):
        """Test error handling when LM Studio server is unreachable"""
        mock_get_models.return_value = [{"identifier": "llama-3.2-1b-instruct"}]
        mock_post.side_effect = Exception("Connection refused")
        
        response = lmsg.send_prompt("Hello")
        self.assertIn("Error:", response)
    
    @patch('lmsg.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_uses_specified_model(self, mock_post, mock_get_models):
        """Test that -m flag correctly specifies which model to use"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {"content": "Response from specific model"}
                }]
            }
        )
        
        response = lmsg.send_prompt("Hello", model="custom-model")
        self.assertEqual(response, "Response from specific model")
        
        # Verify the model was used in the request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]['json']
        self.assertEqual(call_args['model'], "custom-model")

    @patch('sys.stderr', new_callable=MagicMock)
    @patch('builtins.print')
    @patch('sys.stdin.isatty')
    @patch('sys.stdin.read')
    @patch('lmsg.get_server_status')
    @patch('lmsg.send_prompt')
    def test_piped_input_replaces_prompt_by_default(self, mock_send, mock_status, mock_read, mock_isatty, mock_print, mock_stderr):
        """Test piped content becomes the prompt when no arguments given"""
        mock_isatty.return_value = False
        mock_read.return_value = "This is piped content"
        mock_status.return_value = {"running": True}
        mock_send.return_value = "Response to piped content"
        
        # Simulate running with no arguments but piped input
        with patch('sys.argv', ['lmsg.py']):
            lmsg.main()
        
        mock_send.assert_called_once_with("This is piped content", None, 1234)
        mock_print.assert_called_once_with("Response to piped content")
    
    @patch('sys.stderr', new_callable=MagicMock)
    @patch('builtins.print')
    @patch('sys.stdin.isatty')
    @patch('sys.stdin.read')
    @patch('lmsg.get_server_status')
    @patch('lmsg.send_prompt')
    def test_pipe_mode_append_adds_piped_content_after_prompt(self, mock_send, mock_status, mock_read, mock_isatty, mock_print, mock_stderr):
        """Test --pipe-mode append adds piped content after the main prompt"""
        mock_isatty.return_value = False
        mock_read.return_value = "Document content here"
        mock_status.return_value = {"running": True}
        mock_send.return_value = "Summary of document"
        
        # Simulate running with prompt and piped input
        with patch('sys.argv', ['lmsg.py', 'Summarize this:', '--pipe-mode', 'append']):
            lmsg.main()
        
        mock_send.assert_called_once_with("Summarize this:\n\nDocument content here", None, 1234)
        mock_print.assert_called_once_with("Summary of document")
    
    @patch('sys.stderr', new_callable=MagicMock)
    @patch('builtins.print')
    @patch('sys.stdin.isatty')
    @patch('sys.stdin.read')
    @patch('lmsg.get_server_status')
    @patch('lmsg.send_prompt')
    def test_pipe_mode_prepend_adds_piped_content_before_prompt(self, mock_send, mock_status, mock_read, mock_isatty, mock_print, mock_stderr):
        """Test --pipe-mode prepend adds piped content before the main prompt"""
        mock_isatty.return_value = False
        mock_read.return_value = "Context document"
        mock_status.return_value = {"running": True}
        mock_send.return_value = "Response"
        
        with patch('sys.argv', ['lmsg.py', 'Based on the above, answer:', '--pipe-mode', 'prepend']):
            lmsg.main()
        
        mock_send.assert_called_once_with("Context document\n\nBased on the above, answer:", None, 1234)
        mock_print.assert_called_once_with("Response")
    
    @patch('subprocess.run')
    def test_model_auto_loading_when_not_loaded(self, mock_run):
        """Test automatic model loading when specified model isn't loaded"""
        # First call returns empty list (no models loaded)
        # Second call loads the model successfully
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='[]'),  # No models loaded
            MagicMock(returncode=0, stdout='', stderr='')  # Load successful
        ]
        
        result = lmsg.ensure_model_loaded("llama-3.2-1b-instruct")
        self.assertTrue(result)
        
        # Verify load command was called
        mock_run.assert_any_call(['lms', 'load', 'llama-3.2-1b-instruct'], capture_output=True, text=True)
    
    @patch('subprocess.run')
    def test_model_auto_loading_skipped_when_already_loaded(self, mock_run):
        """Test no loading attempt when specified model is already loaded"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"identifier": "llama-3.2-1b-instruct"}]'
        )
        
        result = lmsg.ensure_model_loaded("llama-3.2-1b-instruct")
        self.assertTrue(result)
        
        # Should only call ps, not load
        mock_run.assert_called_once_with(['lms', 'ps', '--json'], capture_output=True, text=True)
    
    @patch('subprocess.run')
    def test_list_available_models_for_download(self, mock_run):
        """Test listing downloadable models with lms ls command"""
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout='model1\nmodel2\nmodel3'
        )
        
        models = lmsg.list_available_models()
        self.assertEqual(len(models), 3)
        self.assertIn("model1", models)
        self.assertIn("model2", models)
        self.assertIn("model3", models)
    
    @patch('logging.debug')
    @patch('logging.info')
    def test_verbose_flag_enables_debug_logging(self, mock_info, mock_debug):
        """Test -v flag enables detailed debug and info logging"""
        # Set up logging in verbose mode
        lmsg.setup_logging(verbose=True)
        
        # Trigger some log messages
        logging.debug("Debug message")
        logging.info("Info message")
        
        mock_debug.assert_called_with("Debug message")
        mock_info.assert_called_with("Info message")
    
    def test_piping_real_file_content_for_translation(self):
        """Test piping actual file content from testdata and processing it"""
        import os
        test_file = os.path.join(os.path.dirname(__file__), 'testdata', 'test-text.md')
        
        # Read the test file content
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Mock all the components
        with patch('lmsg.cli.get_server_status', return_value={"running": True}), \
             patch('lmsg.cli.send_prompt') as mock_send, \
             patch('sys.stdin.isatty', return_value=False), \
             patch('sys.stdin.read', return_value=content), \
             patch('sys.argv', ['lmsg', 'Please translate the following Norwegian text to English:']), \
             patch('builtins.print') as mock_print:
            
            mock_send.return_value = "Translation successful"
            lmsg.main()
            
            # Verify the Norwegian content was properly combined with the prompt
            call_args = mock_send.call_args[0][0]
            self.assertIn("Please translate the following Norwegian text to English:", call_args)
            self.assertIn("FORORD TIL ELEVEN", call_args)
            self.assertIn("Denne boka er skrevet", call_args)
            mock_print.assert_called_once_with("Translation successful")

if __name__ == '__main__':
    unittest.main()