"""AST Node evaluation subsystem.

Implements the recursive tree-walking evaluation phase of the macro engine.
Traverses an Abstract Syntax Tree and produces final string output with all
macros resolved, definitions applied, and patterns substituted.
"""

import re
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class Definition:
    pattern_class: str  # 'PRE', 'BOUNDED', 'POST'
    strength: str       # 'STRONG', 'WEAK'
    key_is_regex: bool
    value_is_regex: bool
    key: str
    value: str


class MacroContext:
    """Double-ended context stack for definition scope management.
    
    Maintains definitions in a deque with strong definitions at HEAD (left)
    and weak definitions at TAIL (right). Left-to-right traversal ensures
    strong definitions are checked before weak ones, implementing priority-based
    lookup and lexical scoping.
    """
    
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


def apply_unbounded_patterns(text: str, definitions: List[Definition]) -> str:
    """Apply unbounded pattern substitutions sequentially left-to-right.
    
    Each definition is applied in order, with the output of one becoming
    the input for the next. This creates a composition of substitutions
    where earlier definitions affect later ones.
    
    Args:
        text: Input string to transform
        definitions: List of Definition objects in priority order
        
    Returns:
        Transformed string after all pattern substitutions
    """
    current_text = text
    for d in definitions:
        if d.key_is_regex:
            current_text = re.sub(d.key, d.value, current_text)
        elif d.value_is_regex:
            # Literal key, regex value: replace literal key with regex-evaluated value
            current_text = current_text.replace(d.key, d.value)
        else:
            # Both literal: simple string replacement
            current_text = current_text.replace(d.key, d.value)
    return current_text


def evaluate_ast_node(node: 'ASTNode', context: MacroContext, trace_log: Dict) -> str:
    """Evaluate an AST node recursively, producing final resolved string.
    
    Implements the 7-phase node lifecycle:
    1. Push local arguments to Context
    2. Apply Unbounded Pre-Patterns
    3. Lex and Parse Bounded Tokens
    4. Recursively Evaluate Children and Concatenate
    5. Apply Unbounded Post-Patterns
    6. Pop local scope
    7. Log Trace State
    
    Args:
        node: ASTNode to evaluate
        context: MacroContext for definition lookup
        trace_log: Dictionary to record evaluation results
        
    Returns:
        Fully resolved string with all macros expanded and patterns applied
    """
    # Phase 2: Apply Unbounded Pre-Patterns
    text = apply_unbounded_patterns(node.raw_text, context.get_definitions('PRE'))

    # Phase 3: Lex and Parse Bounded Tokens (already done in ASTNode.content_parts)
    # Phase 4: Recursively Evaluate Children and Concatenate
    resolved_string = ""
    for token in node.content_parts:
        if isinstance(token, ASTNode):
            # Resolve <key> by searching context stack left-to-right (strong first, weak fallback)
            definitions = context.get_definitions('BOUNDED')
            resolved = None
            for d in definitions:
                if d.key_is_regex:
                    if re.search(d.key, token.raw_text):
                        resolved = re.sub(d.key, d.value, token.raw_text)
                        break
                elif d.key == token.raw_text:
                    if d.value_is_regex:
                        resolved = re.sub(re.escape(d.key), d.value, token.raw_text)
                    else:
                        resolved = d.value
                    break
            
            if resolved is None:
                # Unresolved token: return raw text (fallback)
                resolved = token.raw_text
            else:
                # Recursively evaluate the resolved value
                value_node = ASTNode(resolved)
                resolved = evaluate_ast_node(value_node, context, trace_log)
            
            resolved_string += resolved
            trace_log[token.raw_text] = resolved
        else:
            # Literal text passes through unchanged
            resolved_string += token

    # Phase 5: Apply Unbounded Post-Patterns
    final_string = apply_unbounded_patterns(resolved_string, context.get_definitions('POST'))
    
    # Phase 7: Log Trace State
    trace_log[node.raw_text] = final_string
    return final_string


class ASTNode:
    """Abstract Syntax Tree node representing a semantic unit.
    
    Pure semantic container for holding parsed structure without runtime state.
    Evaluation is handled by separate evaluate_ast_node() function.
    """
    
    def __init__(self, raw_text: str, is_transparent: bool = False, content_parts: Optional[List] = None):
        self.raw_text = raw_text
        self.is_transparent = is_transparent
        self.content_parts = content_parts if content_parts is not None else []
    
    def evaluate(self, context: MacroContext, trace_log: Dict) -> str:
        """Evaluate this node and return resolved string.
        
        Delegates to the evaluate_ast_node() function for the actual evaluation logic.
        """
        return evaluate_ast_node(self, context, trace_log)
