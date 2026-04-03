import re
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

@dataclass
class Definition:
    pattern_class: str  # 'PRE', 'BOUND', 'POST'
    strength: str       # 'STRONG', 'WEAK'
    is_regex: bool
    key: str
    value: str

class MacroContext:
    def __init__(self):
        # Double-ended queue: Head = WEAK, Tail = STRONG
        self.stack: deque[Definition] = deque()

    def push(self, definition: Definition):
        if definition.strength == 'STRONG':
            self.stack.append(definition)
        else:
            self.stack.appendleft(definition)

    def pop_strong(self):
        return self.stack.pop()

    def pop_weak(self):
        return self.stack.popleft()

    def get_definitions(self, pattern_class: str) -> List[Definition]:
        # Returns definitions in Right-to-Left priority (Strongest/Newest first)
        return [d for d in reversed(self.stack) if d.pattern_class == pattern_class]

class ASTNode:
    def __init__(self, raw_text: str, is_transparent: bool = False):
        self.raw_text = raw_text
        self.is_transparent = is_transparent
        self.children = []
    
    def evaluate(self, context: MacroContext, trace_log: Dict) -> str:
        # 1. Apply Pre-Patterns (Unbounded)
        text = self._apply_unbounded(self.raw_text, context.get_definitions('PRE'))
        
        # 2. Lex and Parse Bounded Tokens
        # (Simplified for V1: In production, use a stack-based character scanner here 
        # to find balanced '< >' and '{ }' and construct child ASTNodes)
        parsed_tokens = self._lex_string(text)
        
        # 3. Recursive Evaluation & Concatenation
        resolved_string = ""
        for token in parsed_tokens:
            if isinstance(token, ASTNode):
                # Apply scoping rules
                added_strong, added_weak = self._push_local_args(token, context)
                
                # Recurse
                resolved_child = token.evaluate(context, trace_log)
                resolved_string += resolved_child
                
                # Pop scope (unless transparent)
                if not token.is_transparent:
                    for _ in range(added_strong): context.pop_strong()
                    for _ in range(added_weak): context.pop_weak()
            else:
                resolved_string += token # Literal text

        # 4. Apply Post-Patterns (Unbounded)
        final_string = self._apply_unbounded(resolved_string, context.get_definitions('POST'))
        
        # 5. Log Trace
        trace_log[self.raw_text] = final_string
        return final_string

    def _apply_unbounded(self, text: str, definitions: List[Definition]) -> str:
        # Executes Left-to-Right sequentially using Right-to-Left prioritized definitions
        current_text = text
        for d in definitions:
            if d.is_regex:
                # Standard Python re.sub
                current_text = re.sub(d.key, d.value, current_text)
            else:
                current_text = current_text.replace(d.key, d.value)
        return current_text

    def _lex_string(self, text: str):
        # Placeholder for the pushdown automaton lexer.
        # Should return a list mixing strings (literals) and ASTNodes (macros).
        return [text]

    def _push_local_args(self, token: 'ASTNode', context: MacroContext) -> Tuple[int, int]:
        # Parses token arguments (e.g., <key|arg:val>) and pushes to context.
        # Returns number of (strong, weak) definitions added to manage popping.
        return (0, 0)

class PromptEngine:
    def __init__(self, global_context_string: str):
        self.global_context = MacroContext()
        self._parse_global_context(global_context_string)

    def _parse_global_context(self, context_string: str):
        # Parses the orthogonal syntax matrix (:<, :, :>) and populates self.global_context
        pass

    def generate(self, prompt: str) -> Tuple[str, Dict]:
        trace_log = {}
        root = ASTNode(prompt, is_transparent=True)
        final_prompt = root.evaluate(self.global_context, trace_log)
        return final_prompt, trace_log