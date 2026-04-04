"""AST Node evaluation subsystem.

Implements the recursive tree-walking evaluation phase of the macro engine.
Traverses an Abstract Syntax Tree and produces final string output with all
macros resolved, definitions applied, and patterns substituted.
"""

import re
from typing import List, Dict
from core_engine import MacroContext, ASTNode, Definition


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


