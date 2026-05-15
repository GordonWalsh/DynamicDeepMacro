import itertools
import re
from typing import Tuple, Dict, Optional, List, Type
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto

class TokenType(Enum):
    # SYNTAXOID? TOKENOID? Not sure if we need those root or pre-buckets.
    SPLIT = auto()                  # Zero-depth Segment dividers (|)
    MODIFIER = auto()               # Math/Quantity rules (2$$)
    SCOPE = auto()                  # Raw Text wrapped ({ }) for deferred Evaluation
    
    TEXTOID = auto()                # Text content of unknown variety
    RAW = auto()                    # Raw Text unprocessed by the engine. TODO: Not sure if there is a distinct type for may-contain-syntax vs clean-of-syntax but subject to other modification that could induce syntax later?
    LITERAL = auto()                # Text that is already, or will not be, Evaluated and is now inert
    REGEX = auto()                  # Text that is intended to be used as a regex pattern/substitution for matching during evaluation
    
    INVOCATIONOID = auto()          # <>-wrapped text of any type, various Invocations or Escape Block
    INVOCATION_SCOPED = auto()
    INVOCATION_UNSCOPED = auto()
    INVOCATION_POSITIONAL = auto()  # Positional argument references (e.g. <1>, <2>, etc.)
    ESCAPE = auto()                 # Escape Block (</.../>) content in its escaped (ASCII) form
    
    DEFINITIONOID = auto()          # Placeholder for Definitions and Arguments pre-classification
    DEFINITION_EAGER = auto()
    DEFINITION_LAZY = auto()
    ARGUMENT_EAGER = auto()
    ARGUMENT_LAZY = auto()
    # TODO Verify that there is nothing special needed for multi-line Definitions

@dataclass(slots=True) # FIXME: recommended to have frozen=true, but not sure if it is necessary
class Token:
    """Represents a classified piece of text content. Saved as indices of a reference string for performance. May be used as a 'virtual string' in contexts outside of lexing output."""
    type: TokenType
    root_string: str    # Reference to the original string the Token indices are for
    start: int          # Inclusive first-character index WRT the root string
    end: int            # Exclusive ending point WRT the root string
    separator_idx: Optional[int] = None # For Definitions Kay-Value Separator. TODO maybe rename to extra_idx?
    
    # TODO Copied in from suggestion, merge with `payload`?
    def __str__(self):
        # Currently just the root string's slice, but might change in the future.
        return self.root_string[self.start:self.end]
    
    def __len__(self):
        return self.end - self.start
    
    def __getitem__(self, key):
        length = self.end - self.start
        if type(key) is int:
            # 1. Handle negative wrapping
            if key < 0:
                key += length
            # 2. Boundary check: Prevent access outside the window
            if key < 0 or key >= length:
                raise IndexError("index out of range")
            # 3. Return character from base string at shifted offset
            return self.root_string[self.start + key]

        if type(key) is slice:
            # slice.indices(n) returns (start, stop, stride) adjusted for length n
            start, stop, step = key.indices(length)
            
            if step is None or step == 1:
                # Return a new View with re-calculated absolute boundaries
                return self.__class__(
                    root_string=self.root_string,
                    start=self.start + start,
                    end=self.start + stop,
                    type=self.type,
                    separator_idx = self.separator_idx # NOTE: Doesn't move relative to the base string. May be outside new bounds, but was valid relative to the original bounds, so keep regardless.
            )
            else:
                # Slicing with a stride forces a copy in Python strings.
                # return self.base_string[self.start + start : self.start + stop : step]
                raise ValueError("Only contiguous slices (step=1) are supported")
        raise TypeError(f"Invalid index type: {type(key)}")

    def __iter__(self):
        # This returns the iterator of the substring
        return iter(self.root_string[self.start:self.end])
    
    def __eq__(self, other):
        """
        Compare tokens based on text and marker_type only.
        
        This allows test assertions to ignore start/end indices, which are
        metadata for internal tracking with the deferred slicing for performance
        rather than semantic reasons, and compare with the actual semantics.
        """
        if isinstance(other, Token):
            if (self.type == other.type):
                if (other.root_string is self.root_string):
                    # TODO not sure if this is enough to handle Definition Tokens safely
                    return (other.start == self.start and other.end == self.end and other.separator_idx == self.separator_idx)
                else:   # Different root string but still may be identical content
                    return self.payload == other.payload # Could do with memoryviews?
        elif isinstance(other, str):
            return self.payload == other # Should this also check for a Textoid Type or subType?
        return False
    
    @property
    def payload(self) -> str:
        """Strictly deferred evaluation. Only slices memory when explicitly requested."""
        return self.root_string[self.start:self.end]
    
    # TODO Need to validate the separator_idx or +1 WRT other functions expectations
    @property
    def key_text(self) -> str:
        """Returns the Key string. Fails safely if not a Definition."""
        if self.separator_idx is None:
            raise ValueError("Token does not have a separator_idx.")
        return self.root_string[self.start : self.separator_idx]

    @property
    def value_text(self) -> str:
        """Returns the Value string. Fails safely if not a Definition."""
        if self.separator_idx is None:
            raise ValueError("Token does not have a separator_idx.")
        return self.root_string[self.separator_idx + 1 : self.end]
    
    @property
    def is_def_type(self) -> bool: # TODO is this needed and/or should it check separator is not None/is valid?
        """Checks if a Token is a Definition type that has a spearator_idx"""
        return self.type == TokenType.DEFINITION_EAGER or self.type == TokenType.DEFINITION_LAZY


 
class DefClass(Enum):
    BOUNDED = auto()
    PRE_PATTERN = auto()
    POST_PATTERN = auto()

class DefPosition(Enum):
    BASE = auto()
    LEFT = auto()
    RIGHT = auto()

# TODO Update Definition for new changes and add DefLibrary stuff.
@dataclass
class Definition:
    """Represents a single Key -> Value Definition with necessary metadata"""
    pattern_class: DefClass  # 'PRE_PATTERN', 'BOUNDED', 'POST_PATTERN'
    position: DefPosition       # 'BASE', 'LEFT', 'RIGHT'
    key: Token
    value: Token
    compiled_pattern: Optional[re.Pattern] = None

    def resolve(self, target: Token) -> Token | None:
        """Compares the target Key Token to the Definition's key using the appropriate matching logic, returning the (possibly Regexed) Payload Value Token if there is a match and None if there iis no match"""
        if self.key.type != TokenType.REGEX: # NOTE: Assuming all non-Regex Tokens that might end up in a Definition's Key are just textoids with the text content as their payload.
            if self.key == target.payload:
                return self.value   # NOTE Definition syntax having non-Regex Keys with Regex Values must be pre-unescaped.
        else:
            match = self.compiled_pattern.fullmatch(target.root_string, pos=target.start, endpos = target.end) # pyright: ignore[reportOptionalMemberAccess] # Parser guarantees
            if match:
                if self.value.type == TokenType.REGEX:
                    # NOTE: I am informed that re.sub is the fastest way to implement this, so it just uses a little funny construction to get there
                    rep_str = match.re.sub(self.value.payload, target.payload)
                    return Token(type = TokenType.RAW, root_string = rep_str, start = 0, end = len(rep_str))
                else:
                    return self.value   # Could be either Raw or Literal, just pass it on
            return None # No match found
        
    def resolve_str(self, target_str: str) -> Token | None:
        """Helper function to resolve against bare strings.
        NOTE: Currently just creates token and calls token version, but could be optimized later if needed"""
        self.resolve(Token(type=TokenType.LITERAL, root_string=target_str, start=0, end=len(target_str)))
        
class DefLibrary:
    """Organizes Definitions by pattern class and strength for efficient lookup and scoping."""
    pre_strong: List[Definition]
    pre_weak: List[Definition]
    bounded_strong: List[Definition]
    bounded_weak: List[Definition]
    post_strong: List[Definition]
    post_weak: List[Definition]
    pre_strong_scope: List[int]
    pre_weak_scope: List[int]
    bounded_strong_scope: List[int]
    bounded_weak_scope: List[int]
    post_strong_scope: List[int]
    post_weak_scope: List[int]

    def get_lengths(self):
        return (len(self.pre_strong), len(self.pre_weak), len(self.bounded_strong), len(self.bounded_weak), len(self.post_strong), len(self.post_weak))

    # TODO Convert to Enums as well, per note in Definition
    def push_strong(self, definition: Definition):
        if definition.pattern_class == DefClass.PRE_PATTERN:
            self.pre_strong.append(definition)
        elif definition.pattern_class == DefClass.BOUNDED:
            self.bounded_strong.append(definition)
        elif definition.pattern_class == DefClass.POST_PATTERN:
            self.post_strong.append(definition)
        else:
            raise ValueError(f"Invalid pattern class: {definition.pattern_class}")
    
    def push_weak(self, definition: Definition):
        if definition.pattern_class == DefClass.PRE_PATTERN:
            self.pre_weak.append(definition)
        elif definition.pattern_class == DefClass.BOUNDED:
            self.bounded_weak.append(definition)
        elif definition.pattern_class == DefClass.POST_PATTERN:
            self.post_weak.append(definition)
        else:
            raise ValueError(f"Invalid pattern class: {definition.pattern_class}")

    def push_scope(self):
        """Push the current lengths onto the stack to mark a new scope level"""
        self.pre_strong_scope.append(len(self.pre_strong))
        self.pre_weak_scope.append(len(self.pre_weak))
        self.bounded_strong_scope.append(len(self.bounded_strong))
        self.bounded_weak_scope.append(len(self.bounded_weak))
        self.post_strong_scope.append(len(self.post_strong))
        self.post_weak_scope.append(len(self.post_weak))
    
    def pop_scope(self):
        """Remove all items past the last scope marker and delete that marker"""
        # TODO It might be better to have this just pop the scopes, and rely on pop_to_scope to handle the actual deletions, for more flexible control over when the deletions happen vs just popping the scopes? Depends on how we want to handle the staging Libraries and their merging into the main Library during Unscoped Invocation processing, which is still TBD.
        del self.pre_strong[self.pre_strong_scope.pop():]
        del self.pre_weak[self.pre_weak_scope.pop():]
        del self.bounded_strong[self.bounded_strong_scope.pop():]
        del self.bounded_weak[self.bounded_weak_scope.pop():]
        del self.post_strong[self.post_strong_scope.pop():]
        del self.post_weak[self.post_weak_scope.pop():]

    def pop_to_scope(self):
        """Remove all items past the last scope marker while retaining that marker"""
        del self.pre_strong[self.pre_strong_scope[-1]:]
        del self.pre_weak[self.pre_weak_scope[-1]:]
        del self.bounded_strong[self.bounded_strong_scope[-1]:]
        del self.bounded_weak[self.bounded_weak_scope[-1]:]
        del self.post_strong[self.post_strong_scope[-1]:]
        del self.post_weak[self.post_weak_scope[-1]:]

    # These get_pattern functions return iterables into the saved lists, rather than instantiating new ones
    def get_active_pre_patterns(self):
        """Get an iterator for pre-patterns contained in the Library"""
        return itertools.chain(reversed(self.pre_strong), self.pre_weak)
    
    def get_active_post_patterns(self):
        """Get an iterator for post-patterns contained in the Library"""
        return itertools.chain(reversed(self.post_strong), self.post_weak)
    
    def get_local_pre_patterns(self):
        """Get an iterator for only the pre-patterns in the outermost (unwrapped) scope layer"""
        return itertools.chain(
            reversed(self.pre_strong[self.pre_strong_scope[-1]:]),
            itertools.islice(self.pre_weak, self.pre_weak_scope[-1], len(self.pre_weak))
        )
    
    def get_local_post_patterns(self):
        """Get an iterator for only the post-patterns in the outermost (unwrapped) scope layer"""
        return itertools.chain(
            reversed(self.post_strong[self.post_strong_scope[-1]:]),
            itertools.islice(self.post_weak, self.post_weak_scope[-1], len(self.post_weak))
        )
    
    # TODO Implement
    def resolve(self, key: str):
        return key
    
    def add_flat(self, other: 'DefLibrary'):
        """Add all Definitions from another Library to the current scope"""
        self.pre_strong.extend(other.pre_strong)
        self.pre_weak.extend(other.pre_weak)
        self.bounded_strong.extend(other.bounded_strong)
        self.bounded_weak.extend(other.bounded_weak)
        self.post_strong.extend(other.post_strong)
        self.post_weak.extend(other.post_weak)

    def refresh_local(self, local_libs: List['DefLibrary']):
        """Clear the current scope and add all Definitions from a list of staging Libraries to the current scope"""
        self.pop_to_scope()
        for lib in local_libs:
            if lib:
                self.add_flat(lib)
    
    def wrap_with(self, other: 'DefLibrary'):
        """Wrap another deep Library, merging the shifted Scope boundaries and then adding the new Library's Definitions"""
        for idx in other.pre_strong_scope:
            self.pre_strong_scope.append(idx + len(self.pre_strong))
        for idx in other.pre_weak_scope:
            self.pre_weak_scope.append(idx + len(self.pre_weak))
        for idx in other.bounded_strong_scope:
            self.bounded_strong_scope.append(idx + len(self.bounded_strong))
        for idx in other.bounded_weak_scope:
            self.bounded_weak_scope.append(idx + len(self.bounded_weak))
        for idx in other.post_strong_scope:
            self.post_strong_scope.append(idx + len(self.post_strong))
        for idx in other.post_weak_scope:
            self.post_weak_scope.append(idx + len(self.post_weak))
        self.add_flat(other)

class PRNG:
    """Pseudorandom number generator for deterministic randomization in pattern reduction and selection."""
    # TODO not sure if seed should be int or string based
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed or 0  # Default seed for reproducibility
    
    def getInt(self, min: int, max: int) -> int:
        """Returns a pseudorandom integer N such that a <= N <= b."""
        return min  # TODO Placeholder implementation
    
    # TODO Add more methods for mutation or other resetting/sequential gets 

class Context:
    """Complete engine state at any particular moment during processing
    
    Maintains definitions in a deque with strong definitions at HEAD (left)
    and weak definitions at TAIL (right). Left-to-right traversal ensures
    strong definitions are checked before weak ones, implementing priority-based
    lookup and lexical scoping.
    """
    # TODO: Need to add initializers for appropriate starting points of these objects, I think?
    library: DefLibrary
    positionals: List[Token]  # Positional arguments for the current scope, if applicable
    prng: PRNG  # PRNG instance for deterministic randomization during evaluation
    trace_log: Dict  # Optional dictionary to record evaluation trace information
    node_ttl: int = 1000  # Example TTL for AST nodes to prevent infinite recursion
    # TODO Should this have a List to store the flattened output TextNodes during final stringification?

class ASTNode:
    """Abstract Syntax Tree node representing a semantic unit.
    
    Pure semantic container for holding parsed structure without runtime state.
    Evaluation is handled by separate evaluate_ast_node() function.
    """
    base_token: Token
    children: List['ASTNode'] = [] # TODO?: How to handle text vs definition vs invocation vs nodes with children?

    def __init__(self, base_token: Token, children: Optional[List] = None):
        self.base_token = base_token
        self.children = children if children is not None else []
    
    # The shared logic you envisioned
    # def _evaluate_scope(self, context: Context, local_defs: list, child_nodes: list) -> str:
        # """Handles context pushing, child iteration, and context popping for any node."""
        # context.push(local_defs)
        # result = "".join(child.execute(context) for child in child_nodes)
        # context.pop(local_defs)
        # return result

    # TODO Not sure if a single universal entry point is a good idea, or if this would be the right type signature to use
    def process(self, context) -> Tuple[List['ASTNode'], Optional[DefLibrary]]:
        """Hook to trigger type-specific internal logic. Most nodes will try to return a list of output Literal TextNodes of their fully evaluated contents and no Library, but some like UnscopedInvocationNodes would return partially processed content with Definitions staged."""
        raise NotImplementedError # Implemented by subclasses
    
    # TODO Not sure if this is the right sort of implementation for the new logic
    def flatten(self) -> List['ASTNode']:
        """Flattens nested nodes into a single-level list for final processing.

        This returns only leaf nodes. When a node has children, the node itself
        is not included in the result; its children are pushed for further
        depth-first traversal.
        """
        # NOTE: Explicit typing to appease the all-knowing type checker that knows that the `self` of `class ASTNode` might not be an ASTNode
        flat_list: List['ASTNode'] = []
        nodes_to_process: List['ASTNode'] = []
        nodes_to_process.append(self)

        while nodes_to_process:
            current_node = nodes_to_process.pop()  # Pop from end (LIFO)
            if current_node.children:
                nodes_to_process.extend(reversed(current_node.children))
            else:
                flat_list.append(current_node)

        return flat_list

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
    

