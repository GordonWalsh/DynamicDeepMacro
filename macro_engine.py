import re
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

@dataclass
class Definition:
    pattern_class: str  # 'PRE', 'BOUND', 'POST'
    strength: str       # 'STRONG', 'WEAK'
    key_is_regex: bool
    value_is_regex: bool
    key: str
    value: str

SYNTAX_CHARACTERS = r'\\:/<>{}'

class MacroContext:
    def __init__(self):
        # Double-ended queue: Head = STRONG, Tail = WEAK
        self.stack: deque[Definition] = deque()

    def push(self, definition: Definition):
        if definition.strength == 'STRONG':
            self.stack.appendleft(definition)
        else:
            self.stack.append(definition)

    def pop_strong(self):
        return self.stack.popleft()

    def pop_weak(self):
        return self.stack.pop()

    def get_definitions(self, pattern_class: str) -> List[Definition]:
        # Returns definitions in natural left-to-right priority (Strongest/Newest first)
        return [d for d in self.stack if d.pattern_class == pattern_class]

class ASTNode:
    def __init__(self, raw_text: str, is_transparent: bool = False, content_parts: Optional[List] = None):
        self.raw_text = raw_text
        self.is_transparent = is_transparent
        self.content_parts = content_parts if content_parts is not None else []
    
    def evaluate(self, context: MacroContext, trace_log: Dict) -> str:
        # ARCHITECTURE: Full AST Node lifecycle as per copilot-instructions.md section 2

        # 1. Push local arguments to Context
        # TODO: Parse <key|arg:val> and <key|arg::val> syntax via _push_local_args
        # (Scoping framework - currently bypassed for simple resolution)
        # added_strong, added_weak = self._push_local_args(self, context)

        # 2. Apply Unbounded Pre-Patterns (Left-to-Right on string and definition order)
        text = self._apply_unbounded(self.raw_text, context.get_definitions('PRE'))

        # 3. Lex and Parse Bounded Tokens (<...> and {...})
        # Proper pushdown automaton in _lex_string handles nesting and escaping.
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
                # CURRENT IMPLEMENTATION: Simple bounded token resolution with recursive evaluation
                # Resolve <key> by searching context stack left-to-right (strong first, weak fallback)
                definitions = context.get_definitions('BOUNDED')
                resolved = None
                for d in definitions:
                    # TODO Smarter Regex handling: Need to handle literals in re.sub safely, and surround regex keys with ^ $ to prevent partial matches, or switch to re.fullmatch for regex keys.
                    # TODO Counterintuitive behavior: If key is regex, it is applied to the token's raw text, not the resolved child text. This may change depending on future decisions about token structure and evaluation order.
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
                    # TODO: Configurable options for unresolved tokens (e.g., empty string, error, or keep as-is)
                    resolved = token.raw_text  # Fallback: return raw text if not found
                else:
                    # Recursively evaluate the value if it contains invocations
                    value_node = ASTNode(resolved)
                    resolved = value_node.evaluate(context, trace_log)
                resolved_string += resolved
                # Log trace
                trace_log[token.raw_text] = resolved
            else:
                # Literal text passes through unchanged
                resolved_string += token

        # 5. Apply Unbounded Post-Patterns (Left-to-Right on string and definition order)
        final_string = self._apply_unbounded(resolved_string, context.get_definitions('POST'))
        
        # 6. Pop local scope
        # TODO: Implement once _push_local_args scoping is complete
        # if not self.is_transparent:
        #     for _ in range(added_strong): context.pop_strong()
        #     for _ in range(added_weak): context.pop_weak()
        
        # 7. Log Trace State
        trace_log[self.raw_text] = final_string
        return final_string

    def _apply_unbounded(self, text: str, definitions: List[Definition]) -> str:
        # Executes Left-to-Right sequentially using left-to-right prioritized definitions
        current_text = text
        for d in definitions:
            # TODO Smarter Regex handling: Just re escape non-regex literals and use re.sub for all, with conditional logic for regex vs literal replacement text
            if d.key_is_regex:
                current_text = re.sub(d.key, d.value, current_text)
            elif d.value_is_regex:
                # apply a literal key replace, but with regex-style replacement text
                current_text = current_text.replace(d.key, d.value)
            else:
                current_text = current_text.replace(d.key, d.value)
        return current_text

    def _lex_string(self, text: str):
        # ARCHITECTURE: Pushdown Automaton / Character-by-Character Lexer
        # This will scan the string character-by-character, tracking:
        # - Current position and escaped state
        # - Stack of open brackets < > for proper nesting
        # - Building token list (literals and ASTNode objects)
        # Tracks escaped characters and nested < ... > frames without regex backtracking.

        main_tokens = []
        stack = []  # each frame is {'parts': [], 'literal': []}
        literal_buffer = []

        def flush_literal_to(target_list):
            nonlocal literal_buffer
            if literal_buffer:
                target_list.append(''.join(literal_buffer))
                literal_buffer = []

        def append_literal(char):
            if stack:
                stack[-1]['literal'].append(char)
            else:
                literal_buffer.append(char)

        i = 0
        while i < len(text):
            ch = text[i]
            # Handle escape sequences for <, >, and backslash
            if ch == '\\' and i + 1 < len(text):
                nxt = text[i + 1]
                if nxt in '<>\\':
                    append_literal(nxt)
                    i += 2
                    continue
                append_literal(ch)
                i += 1
                continue

            if ch == '<':
                # Starting a new bounded token; flush current literal into main tokens or current frame
                if stack:
                    frame = stack[-1]
                    if frame['literal']:
                        frame['parts'].append(''.join(frame['literal']))
                        frame['literal'] = []
                else:
                    flush_literal_to(main_tokens)
                stack.append({'parts': [], 'literal': []})
                i += 1
                continue

            if ch == '>' and stack:
                # Close current bounded token
                frame = stack.pop()
                if frame['literal']:
                    frame['parts'].append(''.join(frame['literal']))
                    frame['literal'] = []

                # Build raw_text as concatenated unresolved content (without delimiters)
                raw_text = ''.join(p.raw_text if isinstance(p, ASTNode) else p for p in frame['parts'])
                node = ASTNode(raw_text, is_transparent=False, content_parts=frame['parts'])

                if stack:
                    stack[-1]['parts'].append(node)
                else:
                    main_tokens.append(node)
                i += 1
                continue

            append_literal(ch)
            i += 1

        # Cleanup at end of string
        if stack:
            # Unclosed < tokens are emitted as literal text (graceful degradation)
            unclosed = ''
            for frame in stack:
                if frame['literal']:
                    frame['parts'].append(''.join(frame['literal']))
                inner = ''.join(p.raw_text if isinstance(p, ASTNode) else p for p in frame['parts'])
                unclosed += '<' + inner
            if literal_buffer:
                unclosed += ''.join(literal_buffer)
            return [unclosed]

        flush_literal_to(main_tokens)

        if not main_tokens:
            return [text]

        # Merge adjacent literal strings (optional normalization)
        normalized = []
        for item in main_tokens:
            if normalized and isinstance(item, str) and isinstance(normalized[-1], str):
                normalized[-1] += item
            else:
                normalized.append(item)

        return normalized

    def _push_local_args(self, token: 'ASTNode', context: MacroContext) -> Tuple[int, int]:
        # Parses token arguments (e.g., <key|arg:val>) and pushes to context.
        # Returns number of (strong, weak) definitions added to manage popping.
        return (0, 0)

class PromptEngine:
    def __init__(self, global_context_string: str):
        self.global_context = MacroContext()
        self._parse_global_context(global_context_string)

    def _unescape(self, text: str) -> str:
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

    def _is_unescaped_slash_delimited(self, text: str) -> bool:
        if len(text) < 2 or not text.startswith('/') or not text.endswith('/'):
            return False
        # Check ending slash is not escaped
        backslashes = 0
        idx = len(text) - 2
        while idx >= 0 and text[idx] == '\\':
            backslashes += 1
            idx -= 1
        return backslashes % 2 == 0

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

            # Find the first unescaped separator (: not preceded by backslash)
            m = re.search(r'(?<!\\):', content)
            if not m:
                continue
            sep_index = m.start()
            if sep_index + 1 < len(content) and content[sep_index + 1] == ':':
                sep = '::'
            else:
                sep = ':'

            raw_key = content[:sep_index]
            raw_value = content[sep_index + len(sep):]
            strength = 'WEAK' if sep == '::' else 'STRONG'

            key_is_regex = self._is_unescaped_slash_delimited(raw_key)
            value_is_regex = self._is_unescaped_slash_delimited(raw_value)

            if key_is_regex:
                key = self._unescape(raw_key[1:-1])
            else:
                key = self._unescape(raw_key)

            if value_is_regex:
                value = self._unescape(raw_value[1:-1])
            else:
                value = self._unescape(raw_value)

            definition = Definition(
                pattern_class=pattern_class,
                strength=strength,
                key_is_regex=key_is_regex,
                value_is_regex=value_is_regex,
                key=key,
                value=value
            )
            self.global_context.push(definition)

    def generate(self, prompt: str, debug: bool=False) -> Tuple[str, Dict]:
        trace_log = {}
        root = ASTNode(prompt, is_transparent=True)
        final_prompt = root.evaluate(self.global_context, trace_log)
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