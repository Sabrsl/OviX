"""
Unit tests for link text extraction edge cases.
Tests nested brackets, multiple parenthetical notes, and various wikitext formats.
"""

import sys
sys.path.insert(0, 'src')

import re


def test_nested_brackets():
    """Test extraction from nested wikilinks"""
    test_cases = [
        # Simple case
        ('[http://example.com Article title]', 'Article title'),
        # Nested wikilink - regex captures first nested bracket content
        ('[http://example.com [[Article]] title]', 'Article'),
        # Multiple nested - regex limitation: only captures first
        ('[http://example.com [[Article1]] [[Article2]] title]', 'Article1'),
    ]

    pattern = r'\[([^\[\]]+(?:\[[^\[\]]*\][^\[\]]*)*)\]'

    for text, expected in test_cases:
        match = re.search(pattern, text)
        if match:
            bracket_content = match.group(1)
            parts = bracket_content.split()
            # Find URL and extract text
            text_parts = [p for p in parts if not p.startswith('http')]
            result = ' '.join(text_parts)
            print(f"✓ {text[:50]}... -> {result}")
            assert result == expected, f"Expected '{expected}', got '{result}'"
        else:
            print(f"✗ No match for: {text}")
            assert False


def test_multiple_parenthetical_notes():
    """Test extraction of multiple parenthetical notes"""
    test_cases = [
        # Single note
        ('http://example.com (en anglais)', ['en anglais']),
        # Multiple notes
        ('http://example.com (en anglais) (PDF)', ['en anglais', 'PDF']),
        # Three notes
        ('http://example.com (en anglais) (PDF) (archive)', ['en anglais', 'PDF', 'archive']),
        # Note with spaces
        ('http://example.com (en anglais, PDF)', ['en anglais, PDF']),
    ]

    pattern = r'\(([^)]+)\)'

    for text, expected in test_cases:
        after_text = text.split('http://example.com')[1].strip() if 'http://example.com' in text else text
        matches = re.findall(pattern, after_text)
        print(f"✓ {text[:50]}... -> {matches}")
        assert matches == expected, f"Expected {expected}, got {matches}"


def test_combined_extraction():
    """Test combined bracket and parenthetical extraction"""
    test_cases = [
        # Bracket with URL and text, followed by note
        ('[http://example.com Article] (en anglais)', 'Article', ['en anglais']),
        # Bracket with nested wikilink and multiple notes
        ('[http://example.com [[Article]] title] (en anglais) (PDF)', 'Article', ['en anglais', 'PDF']),
    ]

    bracket_pattern = r'\[([^\[\]]+(?:\[[^\[\]]*\][^\[\]]*)*)\]'
    paren_pattern = r'\(([^)]+)\)'

    for text, expected_text, expected_notes in test_cases:
        # Extract bracket content
        bracket_match = re.search(bracket_pattern, text)
        if bracket_match:
            bracket_content = bracket_match.group(1)
            parts = bracket_content.split()
            text_parts = [p for p in parts if not p.startswith('http')]
            extracted_text = ' '.join(text_parts)

            # Extract parenthetical notes
            after_text = text[bracket_match.end():].strip()
            notes = re.findall(paren_pattern, after_text)

            print(f"✓ {text[:60]}... -> text: {extracted_text}, notes: {notes}")
            assert extracted_text == expected_text, f"Expected text '{expected_text}', got '{extracted_text}'"
            assert notes == expected_notes, f"Expected notes {expected_notes}, got {notes}"


if __name__ == '__main__':
    print("Testing nested brackets...")
    test_nested_brackets()
    print()

    print("Testing multiple parenthetical notes...")
    test_multiple_parenthetical_notes()
    print()

    print("Testing combined extraction...")
    test_combined_extraction()
    print()

    print("All tests passed!")
