# Definition Library (`Definition` & `DefLibrary`) Subsystem

This subsystem of the engine Context is composed of `Definition` objects that hold the data for one specific input-text -> output-text instruction from the user, as well as `DefLibrary` containers that store and manage the many `Definition`s that may be in effect at any given moment.

## Definitions

A Definition mainly comprises a Key-Pattern that, when found in the input text, will be replaced by a Value-Pattern in a manner and time specified by the additional features of the Definition creation syntax. While most features of the Definition creation syntax are translated almost directly into the actual `Definition` object, some (notably Timing and Strength) are instead directives on how to ingest and store the Definition and don't end up in the saved data directly.

### Orthogonal Definition Syntax Matrix

The parsing logic for Definition syntax follows the pattern: `[Timing][Class]KeyPattern[Position][Strength]Value`. This fully decouples Evaluation Timing, Class, Position, and Strength, allows fully combinatorial, modular definition logic from simple building blocks. Some combinations may have limited practical applications, but still function correctly according to each individual axis' mandate.

1. **Timing (When should the Value be Evaluated, Definition or Invocation?):**
    - `:` -> Lazy Evaluation (Raw Text stored, Evaluated after Resolution)
    - `::` -> Eager Evaluation (Evaluated at Definition, Literal Text stored)
2. **Class (When does this replacement apply?):**
    - _Empty_ -> Bounded Macro (Explicit invocation keys)
    - `<` -> Unbounded Pre-Pattern (Applied before parsing)
    - `>` -> Unbounded Post-Pattern (Applied after evaluation)
3. **Position (Where does the value go? - Concat Vector):**
    - _Empty_ -> Base Terminator (Overwrites/Sets the root value; standard Regex behavior)
    - `<` -> Left-Concat (Prepends to the base/match)
    - `>` -> Right-Concat (Appends to the base/match)
4. **Strength (Stack Priority - Override Level):**
    - `:` -> Strong (Pushed to "Head", evaluated first, acts as local override)
    - `::` -> Weak (Pushed to "Tail", evaluated last, acts as global fallback)

_Example Combinations:_

- `::key:value` (Eager, Bounded, Base, Strong)
- `:<pattern<::prefix` (Lazy, Pre-Pattern, Left-Concat, Weak)
- `:>pattern>:suffix` (Lazy, Post-Pattern, Right-Concat, Strong)

### The Multi-Line Value Wrapper (`<< >>`)

- To support 'Container Macros' and multi-line values without breaking the zero-depth interval tracking, the engine uses explicit Value Wrappers. If `<<` immediately follows a Definition's strength marker, the Lexer overrides the End-of-Line termination rule for Definitions. It initiates a pushdown automaton to track nested `<<` and `>>` pairs, ensuring that nested blocks (like definitions inside definitions) are safely captured as a single, inert literal string. The engine uses **Strict Newline Capture**; leading and trailing newlines inside the block are kept, granting the user explicit control over text flow at both end's transitions.

### The Regex Identity Trap

Unlike Bounded Macros (which have a single explicit Key-String per Invocation), Unbounded Patterns are applied to a whole string at once. Attempting to apply identical concatenation behavior to these Regex replacements would cause severe confusion. For Unbounded Patterns, using a concat Position (`<` or `>`) instead acts as an automated compiler shorthand that implicitly injects the regex `\g<0>` capture token into the Value Pattern to preserve the matched text, preserving the meaning of the concat Definitions while maintaining the efficient sequential application of Unbounded Definitions.

### Definition Token Handler

Rough pseudocode for how the Definition Token handler would work (TODO should move elsewhere?):

```python
# TODO key and value are Tokens now, with the TokenType replacing the is_regex flags.
def process_definition_token(token, target_library, context=None):
    # 1. Universal Extraction (Shared Lazy + Eager)
    pattern_class, direction, is_strong, key, key_is_regex, value, value_is_regex  = extract_syntax_features(token)

    # 2. The Eager Intercept (The only difference)
    if token.type == TokenType.DEF_EAGER:
        if not context:
            raise CompilerError("Eager definitions require an active Context.")
        literal_val = context.evaluate(raw_value)
        raw_value = f"</{escape_hex(literal_val)}/>"

    # 3. Universal Object Creation
    def_obj = Definition(pattern_class, direction, key, key_is_regex, value, value_is_regex)

    # 4. Universal Routing
    if is_strong:
        target_library.push_strong(def_obj)
    else:
        target_library.push_weak(def_obj)
```

### Individual Definition Resolving

```Python
class Definition:
    # ... slots and init ...

    def resolve_against(self, target_key: Token) -> Token | None:
        if self.key.type == TokenType.RAW:
            if self.key.payload == target_key.payload: # I might have already implemented this in Token.__eq__?
                return self.value_token
            return None

        elif self.key.type == TokenType.REGEX:
            match = re.match(self.key.payload, target_key.payload)
            if match:
                # If there's a match, we can process \g<1> substitutions here
                # and return a newly minted LITERAL token with the formatted string.
                return self._generate_regex_literal(match)
            return None

        else:
            raise ValueError(f"Invalid self.key.type: {self.key.type}")
```

## Library

TODO: Change from `deque`s to `List`s and use index-based tracking. - STATUS: `core_types.py` has a `List`-based implementation, just the documentation here is outdated. - In addition to/instead of `wrap_with`, have an `add_local` that doesn't do Scope-index merging math. - Maybe helper function(s) to get/add 6-Tuple lengths.

The `DefLibrary` is the dedicated Definition-management container for the Macro Engine. It handles the storage, scoping, and retrieval of `Definition` objects that were created explicitly (i.e., byt the user typing in the above creation syntax). It does not handle implicit "Definitions" such as those used by Positional Invocations. It is strictly a storage and lookup mechanism, with some very minor concatenations or Regex substitutions as directed by the contained Definitions; it does not parse Raw Text, manipulate the root user input text, or manage Option Selection probability.

### Library Internal Structure

To optimize lookup speeds and completely eliminate type-checking during resolution sweeps, the library separates Definitions into six isolated `collections.deque` structures based on their Class and Strength.

- **Bounded Deques (Dictionary Lookups):** `bounded_strong`, `bounded_weak`
- **Pre-Pattern Deques (Input Mutation):** `pre_strong`, `pre_weak`
- **Post-Pattern Deques (Output Mutation):** `post_strong`, `post_weak`

### The Search-Terminating Dual-Accumulator

**Trap Avoided:** _Using recursive definitions (`:key: <key> | val`) to build up a Value incrementally._ Recursion forces the engine to eagerly collapse PRNG pools, destroying flat peer-to-peer data structures.
**Trap Avoided:** _Context Stack managing string buffers or sorting logic._

- **The Solution:** Combined Value building happens automatically in the Definition Resolution process with dedicated syntax.
- When a key is requested, the (conceptual model of, built as an iterator over two Lists,) stack searches **Left-to-Right (Head-to-Tail / Strongest-to-Weakest)**.
- It accumulates any Left-Concat (`<:`/`<::`) or Right-Concat (`>:`/`>::`) Definitions it finds. (maybe start with a placeholder base in a deque and append these values, then replace the placeholder when the actual Base when found? Or keep two Lists/stacks for the Concat Definitions, then construct the final container from those and the Base when it terminates?)
- The exact moment it hits a Base definition (`:` or `::`), the search **terminates**, yielding the final ordered list. This natively resolves the need for recursive Definitions while allowing infinite, scoped list extensions.
- Because the first concat-Definitions encountered are those that end up closest to the Base Definition, the Context Stack does **not** need to sort these Definitions or manage left/right string buffers. This naturally builds the string from the **Inside-Out**, perfectly guaranteeing that Local Scope wraps tighter than Global Scope without any complex tracking overhead.

### Scoping & State Management Methods

- **`push_scope()`**: Injects a strict boundary by pushing a `None` sentinel to the appropriate ends of all six deques.
- **`pop_scope()`**: Completely removes the current scope level by popping from all six deques until the `None` sentinels are hit and discarded.
- **`pop_to_scope()`**: Removes all Definitions added in the current scope by popping from all six deques until only the outermost `None` sentinels remain.
- **`push_strong and push_weak(Definition)`**: Routes the provided `Definition` object to the correct deque based on its Class (Bounded/Pre/Post). Within that Class, it inserts based on Strength:
    - **Strong** Definitions are pushed to the Head (Left).
    - **Weak** Definitions are pushed to the Tail (Right).
- **`wrap_with(outer_lib: DefLibrary)`**: Safely merges a localized/staging library (e.g., from an Unscoped Invocation's expansion) into the current library, maintaining internal ordering of each. Performs `strong_deque.extendleft(reversed(inner_lib.strong_deque))` and `weak_deque.extend(inner_lib.weak_deque)` across all three Classes. The use of native Python C-backed `extend` and `extendleft` makes merging vastly faster than iterating through objects individually

### Retrieval & Resolution Methods

- **`resolve(KeyString: str) -> str`**: The core dictionary function. It linearly sweeps _only_ `bounded_strong` followed by `bounded_weak`. It executes Left/Right accumulation geometry, applies regex substitutions (`re.sub()`) if the matched Definition uses Regex, stops searching if a Base strike occurs, and returns the concatenated Raw Text.
    - TODO: Would there be any reason to choose to Lex the accumulated Definition Payloads before applying Left/Right accumulation? This would prevent individual Token boundaries from crossing different Definitions, but still pass through behaviors like appending a `SPLIT` Token then a `TEXT` Token to add a PRNG Option to a Base Definition. It would also mean that doing something like adding a Definition as part of the accumulated Value would be simpler as it would only have to care about the characters in the appending Definition to ensure the Payload is Lexed into the correct Definition-type Token, instead of worring about what the Raw Text concatenation might produce. It might also have implications regarding Block Values?
- **Pattern Getters**: Because the deques are pre-sorted by Class, fetching patterns is highly optimized.
    - **`get_active_pre_patterns()` / `get_active_post_patterns()`**: Returns a combined, ordered list of all Strong and Weak patterns for the specified class, ready to be applied to a Payload or Literal String.
    - **`get_local_pre_patterns()` / `get_local_post_patterns()`**: Iterates from the outer edges of the respective deques inward until hitting the first `None` sentinel, returning only the patterns registered in the most-recent execution scope.

### Architectural Design Decisions

1. **Flat Deques over Layered Stacks:**
    - _Rejected:_ Storing a "Stack of Layers" (where each layer is a dict).
    - _Rationale:_ A layered stack requires a highly inefficient down-then-up traversal to respect Strong/Weak priorities. A flat dual-deque structure allows a single, continuous linear sweep (Left-to-Right) spanning both local and inherited contexts.
2. **Type-Based Deque Separation (Indexing):**
    - _Rejected:_ Mixing Pre, Bounded, and Post definitions in a single pair of Strong/Weak deques.
    - _Rationale:_ Bounded Invocations (`<Key>`) vastly outnumber Pattern injections in typical usage. Separating them prevents the `resolve()` sweep from having to manually evaluate and skip over irrelevant Regex Patterns, turning pattern fetching into a direct O(1) list return.
3. **Separation of Parsing:**
    - _Rejected:_ Having `DefLibrary` accept Tokens and parse them into `Definition` objects.
    - _Rationale:_ "Eager" Definitions (`::Key:Value`) explicitly execute their payloads at the moment of parsing. Execution requires a fully populated Context state. Therefore, Parsing must be owned by the active AST Execution walk, while `DefLibrary` remains a pure, state-agnostic storage vessel.
4. **Implicit Strength:**
    - _Rationale:_ The "Strength" of a Definition (`:` vs `::`) is not a lingering property of the data; it is simply an insertion instruction. Once pushed to the Head or Tail of the deque, the object's order relative to the Sentinels dictates its priority.
