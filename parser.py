"""Token to AST parsing subsystem.

Converts Token objects from the Lexer into Abstract Syntax Tree nodes.
Also handles definition syntax parsing for context initialization.
"""

import re
from typing import List, Optional
from evaluator import Definition
from core_engine import ASTNode, Token

def unescape(text: str) -> str:
    """Unescape syntax characters in text.
    
    Only unescapes characters that are part of the macro syntax:
    backslash, colon, angle brackets, and forward slash.
    Preserves backslashes before other characters.
    
    Args:
        text: Text with potential escape sequences
        
    Returns:
        Text with syntax character escapes removed
    """
    SYNTAX_CHARACTERS = r'\\:/<>{}'
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text) and text[i + 1] in SYNTAX_CHARACTERS:
            result.append(text[i + 1])
            i += 2
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def is_regex_pattern(text: str) -> bool:
    """Check if text is wrapped in unescaped forward slashes.
    
    A regex pattern must:
    1. Start with /
    2. End with / (not escaped)
    3. Have at least 2 characters (slashes must not be adjacent)
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be a regex pattern
    """
    if len(text) < 2 or not text.startswith('/') or not text.endswith('/'):
        return False
    # Check ending slash is not escaped
    backslashes = 0
    idx = len(text) - 2
    while idx >= 0 and text[idx] == '\\':
        backslashes += 1
        idx -= 1
    return backslashes % 2 == 0

def parse_token_to_ast_node(token: Token) -> Optional[ASTNode]:
    """Parse a single Token into an ASTNode.
    
    Detects Token types based on marker_type and processes accordingly
    
    Args:
        token: Token to parse"""
    

def parse_invocation(contents: str) -> Optional[ASTNode]:
    """Parse the contents of a bounded token as a macro invocation.

    Args:
        contents: String inside the bounded token (e.g. <...>)
        
    Returns:
        ASTNode representing the macro invocation, or None if parsing fails.
    """
    # Placeholder: just create a simple ASTNode with raw_text set to contents and no children.
    return ASTNode(raw_text=contents, content_parts=[])

def parse_definition_line(line: str) -> Optional[Definition]:
    """Parse a single definition line into a Definition object.
    
    Syntax patterns (see PARSER_SPECIFICATION.md for full grammar):
    - Bounded Strong:  :[KEY]:[VALUE]
    - Bounded Weak:    :[KEY]::[VALUE]
    - Pre Strong:      :<[KEY]:[VALUE]
    - Pre Weak:        :<[KEY]::[VALUE]
    - Post Strong:     :>[KEY]:[VALUE]
    - Post Weak:       :>[KEY]::[VALUE]
    
    Both KEY and VALUE can be literal text or /regex patterns/.
    
    Args:
        line: Definition line to parse
        
    Returns:
        Definition object if line is valid, None otherwise
    """
    line = line.strip()
    if not line:
        return None

    pattern_class = 'BOUNDED'
    strength = 'STRONG'
    content = line
    
    if line.startswith(':<'):
        pattern_class = 'PRE'
        content = line[2:]
    elif line.startswith(':>'):
        pattern_class = 'POST'
        content = line[2:]
    elif line.startswith(':'):
        pattern_class = 'BOUNDED'
        content = line[1:]
    else:
        return None  # Not a definition line

    # Find the first unescaped separator (: not preceded by backslash)
    m = re.search(r'(?<!\\):', content)
    if not m:
        return None
    
    sep_index = m.start()
    if sep_index + 1 < len(content) and content[sep_index + 1] == ':':
        sep = '::'
    else:
        sep = ':'

    raw_key = content[:sep_index]
    raw_value = content[sep_index + len(sep):]
    strength = 'WEAK' if sep == '::' else 'STRONG'

    key_is_regex = is_regex_pattern(raw_key)
    value_is_regex = is_regex_pattern(raw_value)

    if key_is_regex:
        key = unescape(raw_key[1:-1])  # Strip / delimiters and unescape
    else:
        key = unescape(raw_key)

    if value_is_regex:
        value = unescape(raw_value[1:-1])  # Strip / delimiters and unescape
    else:
        value = unescape(raw_value)

    return Definition(
        pattern_class=pattern_class,
        strength=strength,
        key_is_regex=key_is_regex,
        value_is_regex=value_is_regex,
        key=key,
        value=value
    )


def parse_global_context(context_string: str) -> List[Definition]:
    # TODO this is a legacy function that should be replaced by the Token -> ASTNode parser.
    """Parse all definition lines from a context string.
    
    Extracts all definition lines (starting with :) and parses them
    into Definition objects. Non-definition lines are skipped.
    
    FUTURE: This should be merged into a unified lexer that handles both
    definitions and literal text as part of a single AST construction phase.
    Currently, context_string is treated as pure definitions only.
    
    Args:
        context_string: Raw context string containing definition lines
        
    Returns:
        List of parsed Definition objects
    """
    definitions = []
    for line in context_string.split('\n'):
        definition = parse_definition_line(line)
        if definition:
            definitions.append(definition)
    return definitions
