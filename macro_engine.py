"""Macro Engine - Main entry point (legacy compatibility wrapper).

This module provides backward compatibility with the original macro_engine.py interface.
The actual implementation has been refactored into separate modules:
- core_engine.py: PromptEngine orchestrator
- evaluator.py: MacroContext, ASTNode, and evaluation logic
- parser.py: Definition parsing and syntax handling
- lexer.py: Character-by-character lexing

For new code, import directly from the submodules. This file will be deprecated.
"""

# Re-export public API for backward compatibility
from core_engine import PromptEngine
from evaluator import ASTNode, MacroContext, Definition

__all__ = ['PromptEngine', 'ASTNode', 'MacroContext', 'Definition']
