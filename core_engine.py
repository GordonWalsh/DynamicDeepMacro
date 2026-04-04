"""Core macro engine orchestrator.

Implements the main entry point for the macro expansion system.
Coordinates the three-stage processing pipeline: Lexing, Parsing, and Evaluation.

Pipeline:
1. Lexer: Character-by-character scanning to identify boundaries and escapes
2. Parser: Convert tokens into an Abstract Syntax Tree with semantic grouping
3. Evaluator: Recursive tree-walking to produce final resolved output
"""

from typing import Tuple, Dict
from evaluator import MacroContext, ASTNode, evaluate_ast_node
from parser import parse_global_context
from lexer import lex_string


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
