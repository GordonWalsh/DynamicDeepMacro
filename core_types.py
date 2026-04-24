from typing import Tuple, Dict, Optional, List
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

class TokenType(Enum):
    TEXT = auto()     # Plain text
    DEFINITION = auto()  # Bounded macro, pre-pattern, or post-pattern rules
    INVOCATION = auto()  # Context Stack lookup wrappers (< >)
    SCOPE = auto()       # Atomic Raw text wrappers ({ })
    SPLIT = auto()       # Zero-depth option dividers (|)
    MODIFIER = auto()    # Math/Quantity rules (2$$)

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
    position: int
    length: int
    token_type: TokenType
    content: str
    
    def __eq__(self, other):
        """
        Compare tokens based on text and marker_type only.
        
        This allows test assertions to ignore start/end indices, which are
        metadata for internal tracking rather than semantic token properties.
        """
        if isinstance(other, Token):
            return self.content == other.content and self.token_type == other.token_type
        return False

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
    
    # The shared logic you envisioned
    def _evaluate_scope(self, context: MacroContext, local_defs: list, child_nodes: list) -> str:
        """Handles context pushing, child iteration, and context popping for any node."""
        context.push(local_defs)
        result = "".join(child.execute(context) for child in child_nodes)
        context.pop(local_defs)
        return result

    def evaluate(self, context) -> str:
        raise NotImplementedError

# class InvocationNode(ASTNode):
#     def evaluate(self, context):
#         # 1. Get the raw string
#         raw_string = context.get_accumulated_value(self.key)
        
#         # 2. Lex & Parse
#         tokens = lexer.lex(raw_string)
#         local_defs, child_nodes = parser.parse(tokens)
        
#         # 3. Use the inherited base logic to execute the children directly
#         return self._evaluate_scope(context, local_defs, child_nodes)
    
# class ScopeNode(ASTNode):
#     def evaluate(self, context):
#         # 1. Reduce the inline string using PRNG
#         winning_tokens = self.reduce_and_select(self.raw_payload)
        
#         # 2. Parse the winner
#         local_defs, child_nodes = parser.parse(winning_tokens)
        
#         # 3. Execute directly
#         return self._evaluate_scope(context, local_defs, child_nodes)
    

