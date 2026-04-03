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
        # ARCHITECTURE: Full AST Node lifecycle as per copilot-instructions.md section 2
        
        # 1. Push local arguments to Context
        # TODO: Parse <key|arg:val> and <key|arg::val> syntax via _push_local_args
        # (Scoping framework - currently bypassed for simple resolution)
        # added_strong, added_weak = self._push_local_args(self, context)
        
        # 2. Apply Unbounded Pre-Patterns (Left-to-Right on string, Right-to-Left definition priority)
        # text = self._apply_unbounded(self.raw_text, context.get_definitions('PRE'))
        text = self.raw_text
        
        # 3. Lex and Parse Bounded Tokens (<...> and {...})
        # TODO: Proper pushdown automaton in _lex_string to handle nesting and escaping
        parsed_tokens = self._lex_string(text)
        
        # 4. Recursively Evaluate Children and Concatenate
        resolved_string = ""
        for token in parsed_tokens:
            if isinstance(token, ASTNode):
                # SCOPING ARCHITECTURE: Will be used once _push_local_args is implemented
                """
                # Apply scoping rules for local arguments
                added_strong, added_weak = self._push_local_args(token, context)
                
                # Recurse into child
                resolved_child = token.evaluate(context, trace_log)
                resolved_string += resolved_child
                
                # Pop scope markers (unless node is transparent)
                if not token.is_transparent:
                    for _ in range(added_strong): context.pop_strong()
                    for _ in range(added_weak): context.pop_weak()
                """
                # CURRENT IMPLEMENTATION: Simple bounded token resolution
                # Resolve <key> by searching context stack right-to-left
                definitions = context.get_definitions('BOUNDED')
                resolved = None
                for d in definitions:
                    if d.key == token.raw_text:
                        resolved = d.value
                        break
                if resolved is None:
                    resolved = token.raw_text  # Fallback: return raw text if not found
                    # TODO: Configurable options for unresolved tokens (e.g., empty string, error, or keep as-is)
                resolved_string += resolved
                # Log trace
                trace_log[token.raw_text] = resolved
            else:
                # Literal text passes through unchanged
                resolved_string += token

        # 5. Apply Unbounded Post-Patterns (Left-to-Right on string, Right-to-Left definition priority)
        # final_string = self._apply_unbounded(resolved_string, context.get_definitions('POST'))
        final_string = resolved_string
        
        # 6. Pop local scope
        # TODO: Implement once _push_local_args scoping is complete
        # if not self.is_transparent:
        #     for _ in range(added_strong): context.pop_strong()
        #     for _ in range(added_weak): context.pop_weak()
        
        # 7. Log Trace State
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
        # ARCHITECTURE: Pushdown Automaton / Character-by-Character Lexer
        # This will scan the string character-by-character, tracking:
        # - Current position and escaped state
        # - Stack of open brackets < > for proper nesting
        # - Building token list (literals and ASTNode objects)
        # TODO: Implement stack-based balanced-delimiter parser
        
        # TEMPORARY REGEX-BASED APPROACH (to be replaced with proper lexer):
        import re
        tokens = []
        pattern = r'<([^>]*)>'
        last_end = 0
        for match in re.finditer(pattern, text):
            # Add literal text before
            if match.start() > last_end:
                tokens.append(text[last_end:match.start()])
            # Add ASTNode for the content
            content = match.group(1)
            tokens.append(ASTNode(content))
            last_end = match.end()
        # Add remaining literal
        if last_end < len(text):
            tokens.append(text[last_end:])
        return tokens if tokens else [text]

    def _push_local_args(self, token: 'ASTNode', context: MacroContext) -> Tuple[int, int]:
        # Parses token arguments (e.g., <key|arg:val>) and pushes to context.
        # Returns number of (strong, weak) definitions added to manage popping.
        return (0, 0)

class PromptEngine:
    def __init__(self, global_context_string: str):
        self.global_context = MacroContext()
        self._parse_global_context(global_context_string)

    def _parse_global_context(self, context_string: str):
        # Parse newline-separated definitions using syntax composition from syntax.json:
        # - Bounded Strong:  :[KEY]:[VALUE]
        # - Bounded Weak:    :[KEY]::[VALUE]
        # - Pre Strong:      :<[KEY]:[VALUE]
        # - Pre Weak:        :<[KEY]::[VALUE]
        # - Post Strong:     :>[KEY]:[VALUE]
        # - Post Weak:       :>[KEY]::[VALUE]
        for line in context_string.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Determine CLASS and STRENGTH by examining prefixes and separators
            pattern_class = 'BOUNDED'
            strength = 'STRONG'
            content = line
            
            if line.startswith(':<'):
                pattern_class = 'PRE'
                content = line[2:]  # Remove :<
            elif line.startswith(':>'):
                pattern_class = 'POST'
                content = line[2:]  # Remove :>
            elif line.startswith(':'):
                pattern_class = 'BOUNDED'
                content = line[1:]  # Remove :
            else:
                continue  # Skip lines that don't start with :
            
            # Now parse [KEY]::[VALUE] or [KEY]:[VALUE] to determine strength
            # Split on :: first to check for weak, then on : for strong
            if '::' in content:
                parts = content.split('::', 1)
                if len(parts) == 2:
                    key, value = parts
                    strength = 'WEAK'
                else:
                    continue
            elif ':' in content:
                parts = content.split(':', 1)
                if len(parts) == 2:
                    key, value = parts
                    strength = 'STRONG'
                else:
                    continue
            else:
                continue  # No separator found
            
            # Determine if key/value are regex (enclosed in /) or literal
            key_is_regex = key.startswith('/') and key.endswith('/')
            value_is_regex = value.startswith('/') and value.endswith('/')
            
            definition = Definition(
                pattern_class=pattern_class,
                strength=strength,
                is_regex=key_is_regex or value_is_regex,  # Mark as regex if either is
                key=key,
                value=value
            )
            self.global_context.push(definition)

    def generate(self, prompt: str) -> Tuple[str, Dict]:
        trace_log = {}
        root = ASTNode(prompt, is_transparent=True)
        final_prompt = root.evaluate(self.global_context, trace_log)
        return final_prompt, trace_log