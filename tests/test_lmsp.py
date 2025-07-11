#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lmsp import cli as lmsp
import logging

class TestLmsp(unittest.TestCase):
    
    @patch('subprocess.run')
    def test_get_loaded_models_with_json_output(self, mock_run):
        """Test parsing loaded models from lms ps --json command"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"identifier": "llama-3.2-1b-instruct", "name": "Llama 3.2 1B"}]'
        )
        
        models = lmsp.get_loaded_models()
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
        
        models = lmsp.get_loaded_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["identifier"], "llama-3.2-1b-instruct")
    
    @patch('subprocess.run')
    def test_get_loaded_models_returns_empty_when_none_loaded(self, mock_run):
        """Test returns empty list when no models are loaded"""
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        
        models = lmsp.get_loaded_models()
        self.assertEqual(len(models), 0)
    
    @patch('requests.get')
    @patch('subprocess.run')
    def test_server_status_check_when_running(self, mock_run, mock_get):
        """Test server status detection when LM Studio server is running"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"running": true, "port": 1234}'
        )
        
        status = lmsp.get_server_status()
        self.assertTrue(status["running"])
        self.assertEqual(status["port"], 1234)
    
    @patch('requests.get')
    @patch('subprocess.run')
    def test_server_status_check_when_not_running(self, mock_run, mock_get):
        """Test server status detection when LM Studio server is stopped"""
        mock_run.return_value = MagicMock(returncode=1, stdout='')
        mock_get.side_effect = Exception("Connection refused")
        
        status = lmsp.get_server_status()
        self.assertFalse(status["running"])
    
    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_returns_model_response(self, mock_post, mock_get_models):
        """Test successful prompt sending returns model's response"""
        mock_get_models.return_value = [{"identifier": "llama-3.2-1b-instruct"}]
        
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Hello! "}}]}',
            'data: {"choices":[{"delta":{"content":"How can I help you?"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        response, _ = lmsp.send_prompt("Hello")
        self.assertEqual(response, "Hello! How can I help you?")
    
    def test_send_prompt_fails_when_no_models_loaded(self):
        """Test error message when attempting to send prompt with no loaded models"""
        with patch('lmsp.cli.get_loaded_models', return_value=[]):
            response, _ = lmsp.send_prompt("Hello")
            self.assertIn("No models loaded", response)
    
    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_handles_server_connection_error(self, mock_post, mock_get_models):
        """Test error handling when LM Studio server is unreachable"""
        mock_get_models.return_value = [{"identifier": "llama-3.2-1b-instruct"}]
        mock_post.side_effect = Exception("Connection refused")
        
        response, _ = lmsp.send_prompt("Hello")
        self.assertIn("Error:", response)
    
    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_uses_specified_model(self, mock_post, mock_get_models):
        """Test that -m flag correctly specifies which model to use"""
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Response from specific model"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        response, _ = lmsp.send_prompt("Hello", model="custom-model", stream=False)
        self.assertEqual(response, "Response from specific model")
        
        # Verify the model was used in the request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]['json']
        self.assertEqual(call_args['model'], "custom-model")

    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    @patch('builtins.print')
    def test_send_prompt_streaming_mode(self, mock_print, mock_post, mock_get_models):
        """Test streaming mode outputs tokens as they arrive"""
        mock_get_models.return_value = [{"identifier": "test-model"}]
        
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" there"}}]}',
            'data: {"choices":[{"delta":{"content":"!"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        response, _ = lmsp.send_prompt("Hello", stream=True)
        
        # Verify streaming output was printed as tokens arrived
        print_calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        self.assertIn("Hello", print_calls)
        self.assertIn(" there", print_calls)
        self.assertIn("!", print_calls)
        
        # Verify final response content
        self.assertEqual(response, "Hello there!")

    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_non_streaming_mode(self, mock_post, mock_get_models):
        """Test non-streaming mode waits for complete response"""
        mock_get_models.return_value = [{"identifier": "test-model"}]
        
        # Mock streaming response (non-streaming mode still uses streaming internally)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Complete response"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        response, _ = lmsp.send_prompt("Hello", stream=False)
        self.assertEqual(response, "Complete response")
        
        # Non-streaming mode now uses streaming internally for progress indication
        call_args = mock_post.call_args[1]['json']
        self.assertTrue(call_args['stream'])

    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    def test_send_prompt_strips_trailing_newlines(self, mock_post, mock_get_models):
        """Test that trailing newlines are stripped from responses"""
        mock_get_models.return_value = [{"identifier": "test-model"}]
        
        # Mock streaming response with trailing newlines
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Response with newlines\\n\\n\\n"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        response, _ = lmsp.send_prompt("Hello", stream=False)
        self.assertEqual(response, "Response with newlines")

    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    @patch('builtins.print')
    def test_send_prompt_with_stats(self, mock_print, mock_post, mock_get_models):
        """Test stats collection in streaming mode"""
        mock_get_models.return_value = [{"identifier": "test-model"}]
        
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        response, stats = lmsp.send_prompt("Hello", stream=True, show_stats=True)
        
        # Verify stats are collected
        self.assertIsNotNone(stats)
        self.assertIn('first_token_latency', stats)
        self.assertIn('total_latency', stats)
        self.assertIn('token_count', stats)
        self.assertIn('tokens_per_second', stats)
        self.assertEqual(stats['token_count'], 2)  # "Hello" + " world"

    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    @patch('builtins.print')
    def test_unicode_character_handling(self, mock_print, mock_post, mock_get_models):
        """Test proper Unicode character handling in streaming mode"""
        mock_get_models.return_value = [{"identifier": "test-model"}]
        
        # Mock streaming response with Unicode characters
        streaming_data = [
            'data: {"choices":[{"delta":{"content":"å"}}]}',  # å
            'data: {"choices":[{"delta":{"content":"æ"}}]}',  # æ  
            'data: {"choices":[{"delta":{"content":"ø"}}]}',  # ø
            'data: {"choices":[{"delta":{"content":"日本語"}}]}',  # 日本語
            'data: [DONE]'
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = streaming_data
        mock_post.return_value = mock_response
        
        response, _ = lmsp.send_prompt("Test Unicode", stream=True)
        
        # Verify Unicode characters are properly handled
        self.assertIn('å', response)
        self.assertIn('æ', response) 
        self.assertIn('ø', response)
        self.assertIn('日本語', response)
        
        # Verify correct headers were sent for UTF-8 encoding
        call_kwargs = mock_post.call_args[1]
        self.assertIn('headers', call_kwargs)
        self.assertEqual(call_kwargs['headers']['Content-Type'], 'application/json; charset=utf-8')

    @patch('sys.stderr', new_callable=MagicMock)
    @patch('builtins.print')
    @patch('sys.stdin.isatty')
    @patch('sys.stdin.read')
    @patch('lmsp.cli.get_server_status')
    @patch('lmsp.cli.send_prompt')
    def test_piped_input_replaces_prompt_by_default(self, mock_send, mock_status, mock_read, mock_isatty, mock_print, mock_stderr):
        """Test piped content becomes the prompt when no arguments given"""
        mock_isatty.return_value = False
        mock_read.return_value = "This is piped content"
        mock_status.return_value = {"running": True}
        mock_send.return_value = ("Response to piped content", None)
        
        # Simulate running with -w flag to disable streaming
        with patch('sys.argv', ['lmsp.py', '-w']):
            lmsp.main()
        
        mock_send.assert_called_once_with("This is piped content", None, 1234, stream=False, show_stats=False, plain=False)
        mock_print.assert_called_once_with("Response to piped content")
    
    @patch('sys.stderr', new_callable=MagicMock)
    @patch('builtins.print')
    @patch('sys.stdin.isatty')
    @patch('sys.stdin.read')
    @patch('lmsp.cli.get_server_status')
    @patch('lmsp.cli.send_prompt')
    def test_pipe_mode_append_adds_piped_content_after_prompt(self, mock_send, mock_status, mock_read, mock_isatty, mock_print, mock_stderr):
        """Test --pipe-mode append adds piped content after the main prompt"""
        mock_isatty.return_value = False
        mock_read.return_value = "Document content here"
        mock_status.return_value = {"running": True}
        mock_send.return_value = ("Summary of document", None)
        
        # Simulate running with prompt, piped input, and -w flag
        with patch('sys.argv', ['lmsp.py', 'Summarize this:', '--pipe-mode', 'append', '-w']):
            lmsp.main()
        
        mock_send.assert_called_once_with("Summarize this:\n\nDocument content here", None, 1234, stream=False, show_stats=False, plain=False)
        mock_print.assert_called_once_with("Summary of document")
    
    @patch('sys.stderr', new_callable=MagicMock)
    @patch('builtins.print')
    @patch('sys.stdin.isatty')
    @patch('sys.stdin.read')
    @patch('lmsp.cli.get_server_status')
    @patch('lmsp.cli.send_prompt')
    def test_pipe_mode_prepend_adds_piped_content_before_prompt(self, mock_send, mock_status, mock_read, mock_isatty, mock_print, mock_stderr):
        """Test --pipe-mode prepend adds piped content before the main prompt"""
        mock_isatty.return_value = False
        mock_read.return_value = "Context document"
        mock_status.return_value = {"running": True}
        mock_send.return_value = ("Response", None)
        
        with patch('sys.argv', ['lmsp.py', 'Based on the above, answer:', '--pipe-mode', 'prepend', '-w']):
            lmsp.main()
        
        mock_send.assert_called_once_with("Context document\n\nBased on the above, answer:", None, 1234, stream=False, show_stats=False, plain=False)
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
        
        result = lmsp.ensure_model_loaded("llama-3.2-1b-instruct")
        self.assertTrue(result)
        
        # Verify load command was called
        mock_run.assert_any_call(['lms', 'load', 'llama-3.2-1b-instruct'], capture_output=True, text=True, shell=False, timeout=120)
    
    @patch('subprocess.run')
    def test_model_auto_loading_skipped_when_already_loaded(self, mock_run):
        """Test no loading attempt when specified model is already loaded"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"identifier": "llama-3.2-1b-instruct"}]'
        )
        
        result = lmsp.ensure_model_loaded("llama-3.2-1b-instruct")
        self.assertTrue(result)
        
        # Should only call ps, not load
        mock_run.assert_called_once_with(['lms', 'ps', '--json'], capture_output=True, text=True, shell=False, timeout=30)
    
    @patch('subprocess.run')
    def test_list_available_models_for_download(self, mock_run):
        """Test listing downloadable models with lms ls command"""
        mock_run.return_value = MagicMock(
            returncode=0, 
            stdout='model1\nmodel2\nmodel3'
        )
        
        models = lmsp.list_available_models()
        self.assertEqual(len(models), 3)
        self.assertIn("model1", models)
        self.assertIn("model2", models)
        self.assertIn("model3", models)
    
    @patch('logging.debug')
    @patch('logging.info')
    def test_verbose_flag_enables_debug_logging(self, mock_info, mock_debug):
        """Test -v flag enables detailed debug and info logging"""
        # Set up logging in verbose mode
        lmsp.setup_logging(verbose=True)
        
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
        with patch('lmsp.cli.get_server_status', return_value={"running": True}), \
             patch('lmsp.cli.send_prompt') as mock_send, \
             patch('sys.stdin.isatty', return_value=False), \
             patch('sys.stdin.read', return_value=content), \
             patch('sys.argv', ['lmsp', 'Please translate the following Norwegian text to English:', '-w']), \
             patch('builtins.print') as mock_print:
            
            mock_send.return_value = ("Translation successful", None)
            lmsp.main()
            
            # Verify the Norwegian content was properly combined with the prompt
            call_args = mock_send.call_args[0][0]
            self.assertIn("Please translate the following Norwegian text to English:", call_args)
            self.assertIn("FORORD TIL ELEVEN", call_args)
            self.assertIn("Denne boka er skrevet", call_args)
            # Verify it's in append mode (prompt first, then content)
            expected_start = "Please translate the following Norwegian text to English:\n\n"
            self.assertTrue(call_args.startswith(expected_start))
            # Verify non-streaming mode was used
            self.assertEqual(mock_send.call_args[1]['stream'], False)
            mock_print.assert_called_once_with("Translation successful")

if __name__ == '__main__':
    unittest.main()