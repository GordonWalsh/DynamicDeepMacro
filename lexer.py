"""
Tokenizing and Lexing Module for Macro Engine

This module contains the core lexing architecture and AST node evaluation logic
for the macro engine's bounded token parsing. It implements a character-by-character
pushdown automaton to handle nested token boundaries and escape sequences.

"""

import re
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

SYNTAX_CHARACTERS = r'\\:/<>{}'

def lex_with_boundaries(text: str, boundaries: List[Tuple[str, str]] = [('{', '}'), ('<', '>')]) -> List[str]:
    r"""
    Split text by balanced top-level boundary markers.
    
    Parses text character-by-character, recognizing boundary start/end pairs
    in priority order (first boundary tuple in list takes precedence).
    Only splits on top-level boundaries; nested markers are preserved
    as-is in the parent token's content.
    
    Respects escape sequences: \< \> \\ are treated as literal characters
    and do not trigger boundary logic.
    
    Args:
        text (str): Raw text to tokenize
        boundaries (List[Tuple[str, str]]): List of (start_marker, end_marker)
                                            tuples in priority order.
                                            Assumes single-character markers.
    
    Returns:
        List[str]: Flat list where elements are either literal strings or
                   complete bounded tokens (markers attached to content).
                   Empty boundaries like `<>` are included as valid tokens.
    
    Example:
        >>> lex_with_boundaries("hello <world> and {test} end", [('<', '>'), ('{', '}')])
        ['hello ', '<world>', ' and ', '{test}', ' end']
    """
    result = []
    literal_buffer = []
    boundary_stack = []  # Track open boundaries: [{'start': str, 'end': str, 'content': [], 'nesting_depth': int}]
    
    i = 0
    while i < len(text):
        ch = text[i]
        
        # Handle escape sequences: \<, \>, \\
        if ch == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in SYNTAX_CHARACTERS:  # Escaped syntax character
                if boundary_stack:
                    boundary_stack[-1]['content'].append(ch)
                    boundary_stack[-1]['content'].append(nxt)
                else:
                    literal_buffer.append(ch)
                    literal_buffer.append(nxt)
                i += 2
                continue
            # Backslash not followed by syntax char: treat as literal
            if boundary_stack:
                boundary_stack[-1]['content'].append(ch)
            else:
                literal_buffer.append(ch)
            i += 1
            continue
        
        # Try to match a boundary start (only when not already in a boundary)
        if not boundary_stack:
            matched_boundary = None
            for start, end in boundaries:
                if ch == start:
                    matched_boundary = (start, end)
                    break
            
            if matched_boundary:
                # Flush current literal string to result
                if literal_buffer:
                    result.append(''.join(literal_buffer))
                    literal_buffer = []
                # Open new boundary frame
                boundary_stack.append({
                    'start': matched_boundary[0],
                    'end': matched_boundary[1],
                    'content': [],
                    'nesting_depth': 0
                })
                i += 1
                continue
        else:
            # Inside a boundary: check if this character opens a nested same-type boundary
            if ch == boundary_stack[-1]['start']:
                boundary_stack[-1]['nesting_depth'] += 1
                boundary_stack[-1]['content'].append(ch)
                i += 1
                continue
            # Inside a boundary: check if this character closes it
            if ch == boundary_stack[-1]['end']:
                if boundary_stack[-1]['nesting_depth'] > 0:
                    # This closes a nested boundary, not the outermost one
                    boundary_stack[-1]['nesting_depth'] -= 1
                    boundary_stack[-1]['content'].append(ch)
                else:
                    # This closes the outermost boundary
                    frame = boundary_stack.pop()
                    bounded_token = frame['start'] + ''.join(frame['content']) + frame['end']
                    result.append(bounded_token)
                i += 1
                continue
        
        # Regular character: add to current context
        if boundary_stack:
            boundary_stack[-1]['content'].append(ch)
        else:
            literal_buffer.append(ch)
        i += 1
    
    # Cleanup: handle unclosed boundaries and remaining literal text
    if boundary_stack:
        # Unclosed boundaries: emit as literal text
        unclosed = ''
        for frame in boundary_stack:
            unclosed += frame['start'] + ''.join(frame['content'])
        if literal_buffer:
            unclosed += ''.join(literal_buffer)
        
        # If there are elements in result, append unclosed to the last element
        # Otherwise, append as a new element
        if result:
            result[-1] += unclosed
        else:
            result.append(unclosed)
    else:
        # No unclosed boundaries: flush remaining literal
        if literal_buffer:
            result.append(''.join(literal_buffer))
    
    return result