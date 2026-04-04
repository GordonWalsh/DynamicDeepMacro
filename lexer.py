"""
Tokenizing and Lexing Module for Macro Engine

This module contains the core lexing architecture for the macro engine's bounded 
token parsing. It implements an Interval-Tracking Speculative Lexer that uses 
zero-copy index tracking to handle nested token boundaries and escape sequences.

Core Architecture:
- Uses independent stacks per marker type to track opening indices
- Registers candidate intervals when boundary pairs are successfully closed
- Applies culling logic to determine which intervals are top-level vs consumed
- Returns a pure list of Token objects (both bounded and literal text)
- Zero-copy performance: O(N) time complexity via index tracking instead of buffering
"""

import re
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union


SYNTAX_CHARACTERS = r'\\:/<>{}'


@dataclass
class Token:
    """
    Represents a lexed token: either a bounded token or a literal text span.
    
    Attributes:
        start_idx (int): Index of opening marker (or start of literal) in original text
        end_idx (int): Index of closing marker (or end of literal) in original text
        marker_type (Tuple[str, str]): (start_marker, end_marker) tuple for bounded tokens,
                                       ('', '') for literal text spans
        text (str): Complete token text (with markers for bounded tokens, plain text for literals)
    """
    start_idx: int
    end_idx: int
    marker_type: Tuple[str, str]
    text: str
    
    def __eq__(self, other):
        """
        Compare tokens based on text and marker_type only.
        
        This allows test assertions to ignore start/end indices, which are
        metadata for internal tracking rather than semantic token properties.
        """
        if isinstance(other, Token):
            return self.text == other.text and self.marker_type == other.marker_type
        return False



def lex_with_boundaries(text: str, boundaries: List[Tuple[str, str]] = [('{', '}'), ('<', '>')]) -> List[Token]:
    r"""
    Interval-Tracking Speculative Lexer using zero-copy index tracking.
    
    Parses text character-by-character, maintaining independent stacks for each
    marker type. When a boundary pair closes successfully, registers a candidate
    interval. At EOF, applies culling logic to determine which intervals are
    top-level (not consumed by others).
    
    Respects escape sequences: \< \> \\ are treated as literal characters
    and do not trigger boundary logic.
    
    TODO: Consider adding support for multi-character markers in the future, but for now we assume single-character markers for simplicity.
    TODO: Validate logic for 3+ marker types and priority interleaving at multiple levels.
    TODO: Handle escaping of boundary characters dynamically based on the provided boundaries list, rather than hardcoding SYNTAX_CHARACTERS.
    TODO: Validating that the provided boundaries list does not contain duplicates or conflicting markers would be a good enhancement to prevent ambiguous parsing scenarios.
    TODO: Decide on behavior for very odd cases, like sharing an opening marker but different closing markers, or vice versa, or one marker being a substring of another, or identical opening and closing markers. For now we assume well-formed, non-overlapping marker sets.

    Args:
        text (str): Raw text to tokenize
        boundaries (List[Tuple[str, str]]): List of (start_marker, end_marker)
                                            tuples in priority order.
                                            Assumes single-character markers.
    
    Returns:
        List[Token]: Flat list of tokens. Bounded tokens have marker_type set to 
                     the (start_marker, end_marker) tuple. Literal text spans have 
                     marker_type=('', '').
    
    Example:
        >>> result = lex_with_boundaries("hello <world> and {test} end", [('<', '>'), ('{', '}')])
        >>> # Returns: [Token(text='hello ', marker_type=('', '')), 
        >>> #           Token(text='<world>', marker_type=('<', '>')), 
        >>> #           Token(text=' and ', marker_type=('', '')),
        >>> #           Token(text='{test}', marker_type=('{', '}')), 
        >>> #           Token(text=' end', marker_type=('', ''))]
    """
    # Build marker type lookup: maps each marker char to its type and closing char
    marker_to_type = {}  # marker_char -> (type_id, closing_char)
    marker_stacks = defaultdict(list)  # type_id -> [opening_indices]
    candidate_intervals = []  # [(start_idx, end_idx, type_id)]
    
    for idx, (start_marker, end_marker) in enumerate(boundaries):
        marker_to_type[start_marker] = (idx, end_marker)
        marker_to_type[end_marker] = (idx, start_marker)
    
    # Single-pass lexing: track opening indices and register closed intervals
    i = 0
    while i < len(text):
        ch = text[i]
        
        # Handle escape sequences: \<, \>, \\, etc.
        if ch == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in SYNTAX_CHARACTERS:
                # Escaped syntax character: skip both and continue
                i += 2
                continue
            # Backslash not followed by syntax char: continue normally
            i += 1
            continue
        
        # Check if this is a known marker
        if ch in marker_to_type:
            type_id, counterpart = marker_to_type[ch]
            
            # Determine if this is an opening or closing marker
            is_opening = ch == boundaries[type_id][0]
            
            if is_opening:
                # Push the opening index onto this marker type's stack
                marker_stacks[type_id].append(i)
            else:
                # Try to pop a matching opening marker from the stack
                if marker_stacks[type_id]:
                    start_idx = marker_stacks[type_id].pop()
                    # Register this successfully closed interval
                    candidate_intervals.append((start_idx, i, type_id))
                # If stack is empty, this closing marker is unmatched (treat as literal)
        
        i += 1
    
    # Culling: determine which intervals are top-level (not consumed by others)
    top_level_intervals = _cull_intervals(candidate_intervals)
    
    # Build result: split text at cut points and interleave with tokens
    return _build_result(text, boundaries, top_level_intervals)


def _cull_intervals(candidate_intervals: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
    """
    Apply hierarchy rules to determine which intervals are top-level.
    
    An interval is consumed if:
    1. It is strictly contained within another interval, OR
    2. It overlaps (but is not nested in) another interval with higher priority
    
    Higher priority = lower type_id (earlier in the boundaries list).
    
    Args:
        candidate_intervals: List of (start_idx, end_idx, type_id) tuples
    
    Returns:
        List of top-level (non-consumed) intervals, sorted by start_idx
    """
    if not candidate_intervals:
        return []
    
    # Sort by start index
    sorted_intervals = sorted(candidate_intervals, key=lambda x: x[0])
    
    # Mark which intervals are consumed
    consumed = set()
    
    for i, (start_i, end_i, type_i) in enumerate(sorted_intervals):
        for j, (start_j, end_j, type_j) in enumerate(sorted_intervals):
            if i != j:
                # Check if interval i is strictly inside interval j
                if start_j < start_i and end_i < end_j:
                    consumed.add(i)
                    break
                
                # Check if intervals overlap (but neither fully contains the other)
                # Overlapping means: NOT (one ends before the other starts)
                if not (end_i < start_j or end_j < start_i):
                    # They overlap
                    # Strictly nested: (start_j < start_i and end_i < end_j) or (start_i < start_j and end_j < end_i)
                    is_nested = (start_j < start_i and end_i < end_j) or (start_i < start_j and end_j < end_i)
                    
                    if not is_nested:
                        # Overlapping but not nested: higher priority wins
                        if type_j < type_i:  # j has higher priority
                            consumed.add(i)
                            break
    
    # Return non-consumed intervals in original order, sorted by start
    return [iv for iv in sorted_intervals if sorted_intervals.index(iv) not in consumed]


def _build_result(text: str, boundaries: List[Tuple[str, str]], 
                   top_level_intervals: List[Tuple[int, int, int]]) -> List[Token]:
    """
    Split text at interval boundaries and build result list of tokens.
    
    Both literal text spans and bounded tokens are wrapped as Token objects.
    Literal tokens have marker_type=('', ''). Bounded tokens have marker_type 
    set to their (start_marker, end_marker) tuple.
    
    Args:
        text: Original input text
        boundaries: List of (start_marker, end_marker) tuples
        top_level_intervals: List of (start_idx, end_idx, type_id) to emit as tokens
    
    Returns:
        List[Token]: Pure token list, where each element is a Token object
    """
    if not top_level_intervals:
        # No tokens: return entire text as a single literal token if non-empty
        if text:
            return [Token(start_idx=0, end_idx=len(text) - 1, marker_type=('', ''), text=text)]
        return []
    
    result = []
    last_end = 0
    
    for start_idx, end_idx, type_id in sorted(top_level_intervals, key=lambda x: x[0]):
        # Add literal text before this token (if any)
        if last_end < start_idx:
            literal_text = text[last_end:start_idx]
            result.append(Token(
                start_idx=last_end,
                end_idx=start_idx - 1,
                marker_type=('', ''),
                text=literal_text
            ))
        
        # Add the bounded token
        token_text = text[start_idx:end_idx + 1]
        token = Token(
            start_idx=start_idx,
            end_idx=end_idx,
            marker_type=boundaries[type_id],
            text=token_text
        )
        result.append(token)
        last_end = end_idx + 1
    
    # Add any remaining literal text
    if last_end < len(text):
        literal_text = text[last_end:]
        result.append(Token(
            start_idx=last_end,
            end_idx=len(text) - 1,
            marker_type=('', ''),
            text=literal_text
        ))
    
    return result
