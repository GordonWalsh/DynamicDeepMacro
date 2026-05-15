"""Token to AST parsing subsystem.

Converts Token objects from the Lexer into Abstract Syntax Tree nodes.
Also handles definition syntax parsing for context initialization.
"""

import codecs
import re
from typing import List, Optional
#from core_types import Definition, DefClass, DefPosition, Token, TokenType, ASTNode
from core_types import *

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
    # Check ending slash is not escaped by walking backwards from second-to-last character and counting for even backslashes
    backslashes = 0
    idx = len(text) - 2
    while idx >= 0 and text[idx] == '\\':
        backslashes += 1
        idx -= 1
    return backslashes % 2 == 0

# TODO key and value are Tokens now, with the TokenType replacing the is_regex flags.
# TODO: Definition syntax having non-Regex Keys with Regex Values Should be replaced with static Raw Text (non-regex) Value; it must be unescaped by either `re.compile(r'^').sub(value, "")` (use re.sub on an empty string with value pattern, raises errors) or `re.compile(r'\\([nrtvfa\\])').sub(lambda m: _ESCAPES[m.group(1)], value)` (find escape sequences and directly replace, no errors but no octals); but not `codecs.decode( , 'unicode_escape')` (replaces many other wrong things).
def process_definition_token(defToken, target_library, context=None):
    # TODO: something about removing escape characters? should be ignored so far but still passing through
    root_string = defToken.root_string
    if defToken.separator_idx is None:
        # TODO separate branch for Arguments?
        raise ValueError("Definition Token must have a separator_idx")
    
    # Phase 1: Check for syntax characters and determine Key + Value content boundaries
    """defToken's start will be before/at the leading :, class is an optional character after that, then the maybe /-wrapped key, then the optional position marker preceding the separator index, which points to the first : of the strong/weak :/::, then the value which may be wrapped in <<>> and then /.../"""
    # TODO: Should this use defToken[] indexing instead of accessing its root_string?

    # Check char after leading ':' for Eager ':'
    key_start = defToken.start + 1
    if root_string[key_start] == ':':
        is_eager = True
        key_start += 1
    else:
        is_eager = False
    
    # Check char after leading ':' for def class syntax '<' or '>'
    class_char = root_string[key_start]
    if class_char == '<':
        def_class = DefClass.PRE_PATTERN
        key_start = defToken.start + 1
    elif class_char == '>':
        def_class = DefClass.POST_PATTERN
        key_start = defToken.start + 1
    else:
        def_class = DefClass.BOUNDED
        key_start = defToken.start
    
    # Check char before first separating ':' for def position syntax '<' or '>'
    pos_char = root_string[defToken.separator_idx - 1]
    if pos_char == '<':
        def_position = DefPosition.LEFT
        key_end = defToken.separator_idx - 1
    elif pos_char == '>':
        def_position = DefPosition.RIGHT
        key_end = defToken.separator_idx - 1
    else:
        def_position = DefPosition.BASE
        key_end = defToken.separator_idx
    
    # Check key for Regex-wrapping /.../, trim if so
    if key_end - key_start > 2 and root_string[key_start] == '/' and root_string[key_end-1] == '/':
        key_type = TokenType.REGEX
        key_start += 1
        key_end -= 1
    else:
        key_type = TokenType.LITERAL # TODO This doesn't get evaluated ever?
    
    # Check char after first separating ':' to see if it is Weak ':', preset value start index
    val_start = defToken.separator_idx + 1
    if root_string[val_start] == ':':
        is_strong = False
        val_start += 1
    else:
        is_strong = True

    # Check for captured trailing newline and inset value end accordingly
    if root_string[defToken.end - 1] == '\n':
        val_end = defToken.end -1
    else:
        val_end = defToken.end
    
    # Check for block value wrappers `<<...>>` and inset
    if key_end - key_start >= 4 and  root_string[val_start:val_start+2] == '<<' and root_string[val_end-2:val_end] == '>>':
        val_start += 2
        val_end -= 2

    # Check value for Regex-wrapping /.../, trim if so
    if val_end - val_start > 2 and root_string[val_start] == '/' and root_string[val_end-1] == '/':
        val_type = TokenType.REGEX
        val_start += 1
        val_end -= 1
    else:
        val_type = TokenType.RAW
    
    key_token = Token(key_type, root_string=root_string, start=key_start, end=key_end)
    # return def_class, def_position, is_strong, key_token, val_token

    # 2: Pre-convert Regex Values if non-Regex Key or Eager-Evaluation
    if val_type == TokenType.REGEX and (key_type != TokenType.REGEX or is_eager):
        # No captures, reduce Regex pattern to Raw Text
        try:
            # Forces the re engine to evaluate escapes and validate backreferences
            val_text = re.sub("^", root_string[val_start:val_end], "")
            val_token = Token(type=TokenType.RAW, root_string=val_text, start=0, end=len(val_text))
            # self.value_token = Token(TokenType.LITERAL, folded_text, 0, len(folded_text))
        except re.error as e:
            raise SyntaxError(f"Invalid eager regex substitution: {e}")
    else: # All RAW Values + Lazy REGEX Values with REGEX Key 
        val_token = Token(type=val_type, root_string=root_string, start=val_start, end=val_end)
    
    # 2. Create Eager or Lazy Value Token
    if is_eager:
        if not context:
            raise ValueError("Eager definitions require an active Context.")
        lit_value_text = context.evaluate(val_token) # TODO I think any wrapping/escaping would be handled if this value needs to be combined with other Raw Text, but not now
        val_token = Token(type=TokenType.LITERAL, root_string=lit_value_text, start=0, end=len(lit_value_text))
    # Leave it alone for Lazy
    key_token = Token(key_type, root_string=root_string, start=key_start, end=key_end)

    # 3. Universal Object Creation
    if (key_token.type == TokenType.REGEX):
        key_regex = re.compile(key_token.payload)
        def_obj = Definition(pattern_class=def_class, position=def_position, key=key_token, value=val_token, compiled_pattern=key_regex)
    else:
        def_obj = Definition(pattern_class=def_class, position=def_position, key=key_token, value=val_token)

    # 4. Universal Routing
    if is_strong:
        target_library.push_strong(def_obj)
    else:
        target_library.push_weak(def_obj)

def extract_def_syntax(defToken: Token):    # Placeholder function to extract pattern_class, direction, strength, key, and value from a definition token.
    # This would involve parsing the defToken's raw_text according to the definition syntax rules.
    # For example, it would check for :<, :>, ::, etc. to determine the pattern class and strength.
    # It would also need to trim the key and value parts of the Definition to remove syntax.
    """defToken's start will be before/at the leading :, class is an optional character after that, then the maybe /-wrapped key, then the optional position marker preceding the separator index, which points to the first : of the strong/weak :/::, then the value which may be wrapped in <<>> and then /.../"""
    # TODO: Should this use defToken[] indexing instead of accessing its root_string?
    if defToken.separator_idx is None:
        # TODO separate branch for Arguments?
        raise ValueError("Definition Token must have a separator_idx")

    # Check char after leading ':' for def class syntax '<' or '>'
    class_char = defToken.root_string[defToken.start + 1]
    if class_char == '<':
        def_class = DefClass.PRE_PATTERN
        key_start = defToken.start + 1
    elif class_char == '>':
        def_class = DefClass.POST_PATTERN
        key_start = defToken.start + 1
    else:
        def_class = DefClass.BOUNDED
        key_start = defToken.start
    
    # Check char before first separating ':' for def position syntax '<' or '>'
    pos_char = defToken.root_string[defToken.separator_idx - 1]
    if pos_char == '<':
        def_position = DefPosition.LEFT
        key_end = defToken.separator_idx - 1
    elif pos_char == '>':
        def_position = DefPosition.RIGHT
        key_end = defToken.separator_idx - 1
    else:
        def_position = DefPosition.BASE
        key_end = defToken.separator_idx
    
    # Check key for Regex-wrapping /.../, trim if so
    if key_end - key_start > 2 and defToken.root_string[key_start] == '/' and defToken.root_string[key_end-1] == '/':
        key_type = TokenType.REGEX
        key_start += 1
        key_end -= 1
    else:
        key_type = TokenType.LITERAL # TODO This doesn't get evaluated ever?
    
    # Check char after first separating ':' to see if it is Weak ':', preset value start index
    if defToken.root_string[defToken.separator_idx + 1] == ':':
        is_strong = True
        val_start = defToken.separator_idx + 2
    else:
        is_strong = False
        val_start = defToken.separator_idx + 1

    # Check for captured trailing newline and inset value end accordingly
    if defToken.root_string[defToken.end - 1] == '\n':
        val_end = defToken.end -1
    else:
        val_end = defToken.end
    
    # Check for block value wrappers `<<...>>` and inset
    if key_end - key_start >= 4 and  defToken.root_string[val_start:val_start+2] == '<<' and defToken.root_string[val_end-2:val_end] == '>>':
        val_start += 2
        val_end -= 2
    else:
        key_type = TokenType.LITERAL # TODO This doesn't get evaluated ever?

    # Check value for Regex-wrapping /.../, trim if so
    if val_end - val_start > 2 and defToken.root_string[val_start] == '/' and defToken.root_string[val_end-1] == '/':
        val_type = TokenType.REGEX
        val_start += 1
        val_end -= 1
    else:
        val_type = TokenType.RAW

    
    key_token = Token(key_type, root_string=defToken.root_string, start=key_start, end=key_end)
    val_token = Token(type=val_type, root_string=defToken.root_string, start=val_start, end=val_end)
    return def_class, def_position, is_strong, key_token, val_token


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
    raise NotImplementedError
    return ASTNode(raw_text=contents, content_parts=[])

# def parse_definition_line(line: str) -> Optional[Definition]:
#     """Parse a single definition line into a Definition object.
    
#     Syntax patterns (see PARSER_SPECIFICATION.md for full grammar):
#     - Bounded Strong:  :[KEY]:[VALUE]
#     - Bounded Weak:    :[KEY]::[VALUE]
#     - Pre Strong:      :<[KEY]:[VALUE]
#     - Pre Weak:        :<[KEY]::[VALUE]
#     - Post Strong:     :>[KEY]:[VALUE]
#     - Post Weak:       :>[KEY]::[VALUE]
    
#     Both KEY and VALUE can be literal text or /regex patterns/.
    
#     Args:
#         line: Definition line to parse
        
#     Returns:
#         Definition object if line is valid, None otherwise
#     """
#     line = line.strip()
#     if not line:
#         return None

#     pattern_class = 'BOUNDED'
#     strength = 'STRONG'
#     content = line
    
#     if line.startswith(':<'):
#         pattern_class = 'PRE'
#         content = line[2:]
#     elif line.startswith(':>'):
#         pattern_class = 'POST'
#         content = line[2:]
#     elif line.startswith(':'):
#         pattern_class = 'BOUNDED'
#         content = line[1:]
#     else:
#         return None  # Not a definition line

#     # Find the first unescaped separator (: not preceded by backslash)
#     m = re.search(r'(?<!\\):', content)
#     if not m:
#         return None
    
#     sep_index = m.start()
#     if sep_index + 1 < len(content) and content[sep_index + 1] == ':':
#         sep = '::'
#     else:
#         sep = ':'

#     raw_key = content[:sep_index]
#     raw_value = content[sep_index + len(sep):]
#     strength = 'WEAK' if sep == '::' else 'STRONG'

#     key_is_regex = is_regex_pattern(raw_key)
#     value_is_regex = is_regex_pattern(raw_value)

#     if key_is_regex:
#         key = unescape(raw_key[1:-1])  # Strip / delimiters and unescape
#     else:
#         key = unescape(raw_key)

#     if value_is_regex:
#         value = unescape(raw_value[1:-1])  # Strip / delimiters and unescape
#     else:
#         value = unescape(raw_value)

#     return Definition(
#         pattern_class=pattern_class,
#         strength=strength,
#         key_is_regex=key_is_regex,
#         value_is_regex=value_is_regex,
#         key=key,
#         value=value
#     )


# def parse_global_context(context_string: str) -> List[Definition]:
#     # TODO this is a legacy function that should be replaced by the Token -> ASTNode parser.
#     """Parse all definition lines from a context string.
    
#     Extracts all definition lines (starting with :) and parses them
#     into Definition objects. Non-definition lines are skipped.
    
#     FUTURE: This should be merged into a unified lexer that handles both
#     definitions and literal text as part of a single AST construction phase.
#     Currently, context_string is treated as pure definitions only.
    
#     Args:
#         context_string: Raw context string containing definition lines
        
#     Returns:
#         List of parsed Definition objects
#     """
#     definitions = []
#     for line in context_string.split('\n'):
#         definition = parse_definition_line(line)
#         if definition:
#             definitions.append(definition)
#     return definitions
