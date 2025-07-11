#!/usr/bin/env python3
import unittest
from lmsp.cli import format_markdown


class TestMarkdownFormatting(unittest.TestCase):
    """Test cases for markdown formatting functionality"""
    
    def test_bold_formatting(self):
        """Test bold text formatting"""
        text = "This is **bold** text"
        result = format_markdown(text)
        self.assertIn('\033[1m', result)  # BOLD code
        self.assertIn('bold', result)
        self.assertIn('\033[0m', result)  # RESET code
        
    def test_italic_formatting(self):
        """Test italic text formatting"""
        text = "This is *italic* text"
        result = format_markdown(text)
        self.assertIn('\033[2m', result)  # DIM code (used for italic)
        self.assertIn('italic', result)
        self.assertIn('\033[0m', result)  # RESET code
        
    def test_code_formatting(self):
        """Test inline code formatting"""
        text = "This is `code` text"
        result = format_markdown(text)
        self.assertIn('\033[94m', result)  # BLUE code
        self.assertIn('code', result)
        self.assertIn('\033[0m', result)  # RESET code
        
    def test_header_formatting(self):
        """Test header formatting"""
        text = "# Header 1\n## Header 2\n### Header 3"
        result = format_markdown(text)
        self.assertIn('\033[96m', result)  # CYAN code
        self.assertIn('\033[1m', result)  # BOLD code
        self.assertIn('Header 1', result)
        self.assertIn('Header 2', result)
        self.assertIn('Header 3', result)
        
    def test_list_with_bold_items(self):
        """Test list formatting with bold items"""
        text = """- **Item 1**
- **Item 2**
- **Item 3**"""
        result = format_markdown(text)
        # Should contain bold formatting for each item
        self.assertEqual(result.count('\033[1m'), 3)  # 3 bold starts
        self.assertIn('Item 1', result)
        self.assertIn('Item 2', result)
        self.assertIn('Item 3', result)
        
    def test_plain_mode(self):
        """Test plain mode strips all formatting"""
        text = "# Header\n**bold** and *italic* and `code`"
        result = format_markdown(text, plain=True)
        # Should not contain any ANSI codes
        self.assertNotIn('\033', result)
        # Should contain plain text
        self.assertIn('Header', result)
        self.assertIn('bold', result)
        self.assertIn('italic', result)
        self.assertIn('code', result)
        # Should not contain markdown symbols
        self.assertNotIn('**', result)
        self.assertNotIn('*italic*', result)
        self.assertNotIn('`', result)
        self.assertNotIn('#', result)
        
    def test_mixed_formatting(self):
        """Test mixed formatting in single line"""
        text = "This has **bold**, *italic*, and `code` all together"
        result = format_markdown(text)
        self.assertIn('\033[1m', result)  # BOLD
        self.assertIn('\033[2m', result)  # DIM (italic)
        self.assertIn('\033[94m', result)  # BLUE (code)
        
    def test_no_formatting(self):
        """Test text without any markdown formatting"""
        text = "This is plain text with no formatting"
        result = format_markdown(text)
        # Should not add any formatting codes except what might be in the original
        self.assertEqual(text, result.replace('\033[0m', '').replace('\033[1m', '').replace('\033[2m', '').replace('\033[94m', '').replace('\033[96m', ''))


if __name__ == '__main__':
    unittest.main()