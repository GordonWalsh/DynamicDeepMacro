"""Core macro engine orchestrator.

Implements the main entry point for the macro expansion system.
Coordinates the three-stage processing pipeline: Lexing, Parsing, and Evaluation.

Pipeline:
1. Lexer: Character-by-character scanning to identify boundaries and escapes
2. Parser: Convert tokens into an Abstract Syntax Tree with semantic grouping
3. Evaluator: Recursive tree-walking to produce final resolved output
"""

from typing import Tuple, Dict, Optional, List
from collections import deque
from evaluator import MacroContext, ASTNode, evaluate_ast_node
from parser import parse_global_context
from lexer import lex_string
from dataclasses import dataclass

@dataclass
class Token:
    """
    Represents a lexed token: either a bounded token or a literal text span.
    
    Attributes:
        start_idx (int): Index of opening marker (or start of literal) in original text
        end_idx (int): Index of closing marker (or end of literal) in original text
        type_markers (Tuple[str,str, str]): (Token type, start_marker, end_marker) tuple
                                       ('', '') for literal text spans
        text (str): Complete token text (with markers for bounded tokens, plain text for literals)
    """
    start_idx: int
    end_idx: int
    marker_type: Tuple[str, str, str]
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

@dataclass
class Definition:
    pattern_class: str  # 'PRE', 'BOUNDED', 'POST'
    strength: str       # 'STRONG', 'WEAK'
    key_is_regex: bool
    value_is_regex: bool
    key: str
    value: str


@dataclass
class ASTNode:
    """Abstract Syntax Tree node representing a semantic unit.
    
    Pure semantic container for holding parsed structure without runtime state.
    Evaluation is handled by separate evaluate_ast_node() function.
    """
    raw_text: str
    children: List['ASTNode'] = None # TODO: How to handle text vs definition vs invocation vs nodes with children?
    is_transparent: bool = False  # If True, this node doesn't push/pop scope to context

    def __init__(self, raw_text: str, is_transparent: bool = False, content_parts: Optional[List] = None):
        self.raw_text = raw_text
        self.is_transparent = is_transparent
        self.content_parts = content_parts if content_parts is not None else []
    
    def evaluate(self, context: MacroContext) -> str:
        """Evaluate this node and return resolved string.
        
        Delegates to the evaluate_ast_node() function for the actual evaluation logic.
        """
        return evaluate_ast_node(self, context)

class MacroContext:
    """Double-ended context stack for definition scope management.
    
    Maintains definitions in a deque with strong definitions at HEAD (left)
    and weak definitions at TAIL (right). Left-to-right traversal ensures
    strong definitions are checked before weak ones, implementing priority-based
    lookup and lexical scoping.
    """
    trace_log: Dict = None  # Optional dictionary to record evaluation trace information
    def __init__(self):
        # Double-ended queue: Head = STRONG, Tail = WEAK
        self.stack: deque[Definition] = deque()

    def push(self, definition: Definition):
        """Add definition to context stack based on strength.
        
        Strong definitions push to HEAD (left) and override weak definitions.
        Weak definitions push to TAIL (right) and serve as fallbacks.
        """
        if definition.strength == 'STRONG':
            self.stack.appendleft(definition)
        else:
            self.stack.append(definition)

    def pop_strong(self) -> Definition:
        """Remove most recent strong definition from HEAD."""
        return self.stack.popleft()

    def pop_weak(self) -> Definition:
        """Remove oldest weak definition from TAIL."""
        return self.stack.pop()

    def get_definitions(self, pattern_class: str) -> List[Definition]:
        """Get all definitions of a pattern class in priority order (left-to-right).
        
        Returns definitions in natural iteration order where strong definitions
        (at HEAD) are encountered before weak definitions (at TAIL).
        """
        return [d for d in self.stack if d.pattern_class == pattern_class]

class PromptEngine:
    """Main macro expansion engine.
    
    Manages the three-stage pipeline:
    1. Initialize context with global definitions
    2. Lex prompt text to identify boundaries and escapes
    3. Parse into AST (future unified step)
    4. Evaluate AST recursively to produce final output
    
    UNIFIED PARSING ARCHITECTURE PLAN:
    
    Current state (dual pipeline):
    - parse_global_context() parses definition lines to initialize context
    - Prompt is lexed to find bounded tokens < >
    - Pre/Post patterns applied before/after AST resolution
    
    Future unified state (single pipeline):
    Global context and prompt would be unified into a single input processed by
    a single character-by-character lexer capable of handling:
    1. Definition syntax (:[KEY]:[VALUE]) appearing anywhere
    2. Bounded token boundaries (< >) and nested structures
    3. Literal text preservation with proper newline handling
    4. Escape sequence handling for all syntax characters
    
    This would produce a mixed AST with Definition, Literal, and Invocation nodes.
    Benefits:
    - True local scoping: definitions in one subtree don't leak to siblings
    - Definitions can reference other definitions
    - No artificial separation between "global" and "local" context
    - Identical parsing rules throughout
    """
    
    def __init__(self, global_context_string: str):
        """Initialize engine with global context definitions.
        
        Parses definition lines from the context string and populates
        the global definition stack.
        
        Args:
            global_context_string: Multi-line string containing definitions
                                   (lines starting with :)
        """
        self.global_context = MacroContext()
        definitions = parse_global_context(global_context_string)
        for definition in definitions:
            self.global_context.push(definition)

    def generate(self, prompt: str, debug: bool = False) -> Tuple[str, Dict]:
        """Expand macros in prompt using global context definitions.
        
        Executes the full three-stage pipeline:
        1. Lex prompt to identify boundaries
        2. Parse into AST (currently minimal, future unified)
        3. Evaluate AST recursively
        
        Args:
            prompt: Text containing macro invocations and patterns
            debug: If True, print detailed trace information
            
        Returns:
            Tuple of (final_prompt, trace_log)
            - final_prompt: Fully expanded and resolved text
            - trace_log: Dictionary mapping intermediate values to resolved values
        """
        trace_log = {}
        
        # Create root AST node with prompt text
        # (In current implementation, lexing happens during evaluation via _lex_string)
        root = ASTNode(prompt, is_transparent=True)
        
        # Evaluate the AST recursively
        final_prompt = evaluate_ast_node(root, self.global_context, trace_log)
        
        if debug:
            print('--- DEBUG TRACE ---')
            print('prompt:', prompt)
            print('final_prompt:', final_prompt)
            print('context stack:')
            for d in self.global_context.stack:
                print(' ', d)
            print('trace log:')
            for k, v in trace_log.items():
                print(' ', k, '=>', v)
            print('--- END DEBUG ---')
        
        return final_prompt, trace_log
