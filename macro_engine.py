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
        r"""ARCHITECTURE: Full AST Node lifecycle as per copilot-instructions.md section 2

        1. Push local arguments to Context
        2. Apply Unbounded Pre-Patterns (Left-to-Right on string and definition order)
        3. Lex and Parse Bounded Tokens (<...> and {...})
        4. Recursively Evaluate Children and Concatenate
        5. Apply Unbounded Post-Patterns
        6. Pop local scope
        7. Log Trace State
        """
        # TODO: Parse <key|:arg:val> and <key|:arg::val> syntax via _push_local_args
        # TODO Add scope markers to context stack if not transparant, and ensure proper popping after evaluation of children. Transparent nodes should not push scope markers, allowing their definition to bleed over to their siblings.
        # Scope is controlled by the parent node when invoking the child node, and in most cases the child node will pop any changes it made to the context stack before returning, so that sibling nodes are not affected. However, if the parent node invokes the child node as transparent (e.g., <<child_1>|<child_2>>), then the child node's changes to the context stack will not be popped, allowing them to affect sibling nodes. This allows for flexible scoping rules where some nodes can have isolated local scope while others can share scope with their siblings.
        # Scoping covers more than just arguments passed to the current node; it also covers any definitions that are meant to be local to the current node and its children, which should override global definitions but not affect sibling nodes unless the parent invoked this node as transparent.
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
                # TODO Parse multi-part tokens (e.g., <key|:arg:val>)
                # TODO Check if token key contains other token invocations or parsing boundaries that need to be resolved before context lookup
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
        r"""Character-by-character Pushdown Automaton Lexer
        
        CURRENT SCOPE: Parses bounded token boundaries < > in prompt text only.
        Produces a mixed token list of literal strings and ASTNode objects.
        
        FUTURE SCOPE (unified architecture): This should also:
        - Detect and parse definition lines (starting with :)
        - Handle escaped characters across all syntax (not just < > \)
        - Create Definition nodes in addition to Invocation and Literal nodes
        - Support line-by-line definition detection while preserving literal text
        
        Properly handles:
        - Escaped delimiters (\< \> \\)
        - Nested token boundaries (< < > >)
        - Unclosed tokens (graceful degradation)
        - Preservation of literal text with newlines
        
        Stack frame structure: {'parts': [...], 'literal': [...]}
        - 'parts': mixed list of literal strings and nested ASTNode objects
        - 'literal': character buffer for current literal span
        
        FUTURE: Extend to track definition nodes as separate entities,
        with parse routing logic to identify and extract definition syntax
        before lexing bounded tokens.
        """
        # TODO How should newlines be handled in prompts? Should lines be atomic units that cannot be spanned by tokens?
        # TODO Ensure that lines containing definitions in prompts are parsed as definitions and not passed through as literal text without evaluation.
        # TODO Should the lexer handle parsing of definition strings, or should the start of tokens be checked for definition syntax and routed to a separate definition parser?
        # TODO Extend to handle multiple token boundaries (e.g., { ... }). 
        # TODO Handling of contents is different between types of boundaries, so need to track type of boundary in ASTNode and apply different resolution logic in evaluate() based on type.
        # Could also just pass the bounded text with delimiters to the evaluation and let it handle parsing and resolution based on boundary type
        # TODO How to handle intersecting token boundaries (e.g. < { > })? Hierchical nesting should be supported, but whether to resolve either of the tokens in this case and which is TBD

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
        # TODO May need to be refactored as part of the implementation of multi-part token parsing (e.g., <key|:arg:val>) and the scoping framework for local arguments.
        # Parses token arguments (e.g., <key|:arg:val>) and pushes to context.
        # Returns number of (strong, weak) definitions added to manage popping.
        return (0, 0)

class PromptEngine:
    r"""UNIFIED PARSING ARCHITECTURE PLAN:
    
    Current state (dual pipeline):
    - _parse_global_context() parses definition lines line-by-line, creating a Context Stack
    - ASTNode.evaluate() lexes the prompt via _lex_string() to find bounded tokens < >
    - Pre/Post patterns are applied before/after AST resolution
    
    Future unified state (single pipeline):
    The global context string and the prompt string should be unified into a single input
    that is processed by a single character-by-character lexer capable of handling:
    1. Definition syntax (:[KEY]:[VALUE], etc.) appearing anywhere in the input
    2. Bounded token boundaries (< >) and nested structures
    3. Literal text preservation with proper newline handling
    4. Escape sequence handling for all syntax characters
    
    This unified lexer would produce a mixed AST where nodes can be:
    - Definition nodes (push/pop context state)
    - Literal nodes (preserved text with newlines)
    - Invocation nodes (bounded < > tokens to resolve)
    
    Benefits of unification:
    - True local scoping: definitions in one subtree don't leak to siblings unless parent is transparent
    - Definitions can reference other definitions in the same context
    - No artificial separation between "global" and "local" context
    - Prompt text and context definitions use identical parsing rules
    
    Implementation strategy:
    1. Refactor _lex_string to detect and route definition syntax (lines starting with :)
    2. Merge definition parsing into the same character-by-character loop
    3. Extend ASTNode to track definition nodes separately from invocation/literal nodes
    4. Modify evaluate() to process definitions during traversal, managing stack push/pop
    5. Update PromptEngine to accept a single unified input string instead of separate context
    """
    def __init__(self, global_context_string: str):
        self.global_context = MacroContext()
        self._parse_global_context(global_context_string)

    # TODO Update documentation for syntax and agent instructions to reflect the exact proper escaping rules for strings
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
        """
        TEMPORARY IMPLEMENTATION: Line-by-line definition parser
        
        Parses context definition lines using pattern: [PREFIX][KEY][SEPARATOR][VALUE]
        where PREFIX indicates pattern class (:<, :>, or none for bounded),
        SEPARATOR is : for strong or :: for weak.
        
        FUTURE: This should be merged into a unified lexer that handles both
        definitions and literal text as part of a single AST construction phase.
        Currently, context_string is treated as pure definitions (lines starting with :).
        Once unified, context_string would be treated like prompt text: definitions
        push/pop context during AST traversal, and non-definition lines are literal text.
        
        Syntax patterns supported (see syntax.json for full grammar):
        - Bounded Strong:  :[KEY]:[VALUE]
        - Bounded Weak:    :[KEY]::[VALUE]
        - Pre Strong:      :<[KEY]:[VALUE]
        - Pre Weak:        :<[KEY]::[VALUE]
        - Post Strong:     :>[KEY]:[VALUE]
        - Post Weak:       :>[KEY]::[VALUE]
        
        KEY and VALUE can each be either:
        - Literal text: plain string characters
        - Regex pattern: enclosed in / / and interpreted as Python regex
        """
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
        # TODO Parse non-definitions as literal text to add to the evaluation of the prompt itself, allowing context to contain both definitions and literal text.
        # TODO Unify the evaluation of the prompt with the evaluation of the context string, so that definitions and literal text in the context are treated the same as definitions and literal text in the prompt.
        # The prompt and the global context are currently treated as separate strings, but they are really just the "local" and "upstream" contexts of a single evaluation process.
        # We really should not even have a context string as a test input at all, and should just have a single input string that contains both definitions and the prompt text, which is then fully evaluated as a single AST with a single context stack.
        # This would also allow for more complex interactions between definitions and prompt text, such as definitions that reference other definitions in the same context string, or prompt text that contains definitions that are only meant to be used within the prompt itself.
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