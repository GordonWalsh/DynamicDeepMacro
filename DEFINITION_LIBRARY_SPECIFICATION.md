# Definition Library (`DefLibrary`) Subsystem

## Overview

The `DefLibrary` is the dedicated state-management container for the Macro Engine. It handles the storage, scoping, and retrieval of explicit `Definition` objects. It is strictly a storage and lookup mechanism; it does not parse Raw Text, handle inert Positional Arguments, or manage Option Selection probability.

## Internal Structure

To optimize lookup speeds and completely eliminate type-checking during resolution sweeps, the library separates Definitions into six isolated `collections.deque` structures based on their Class and Strength.

- **Bounded Deques (Dictionary Lookups):** `bounded_strong`, `bounded_weak`
- **Pre-Pattern Deques (Input Mutation):** `pre_strong`, `pre_weak`
- **Post-Pattern Deques (Output Mutation):** `post_strong`, `post_weak`

## Core Methods

### Scoping & State Management

- **`push_scope()`**: Injects a strict boundary by pushing a `None` sentinel to the appropriate ends of all six deques.
- **`pop_scope()`**: Completely removes the current scope level by popping from all six deques until the `None` sentinels are hit and discarded.
- **`pop_to_scope()`**: Removes all Definitions added in the current scope by popping from all six deques until only the outermost `None` sentinels remain.
- **`push_strong and push_weak(Definition)`**: Routes the provided `Definition` object to the correct deque based on its Class (Bounded/Pre/Post). Within that Class, it inserts based on Strength:
    - **Strong** Definitions are pushed to the Head (Left).
    - **Weak** Definitions are pushed to the Tail (Right).
- **`wrap_with(outer_lib: DefLibrary)`**: Safely merges a localized/staging library (e.g., from an Unscoped Invocation's expansion) into the current library, maintaining internal ordering of each. Performs `strong_deque.extendleft(reversed(inner_lib.strong_deque))` and `weak_deque.extend(inner_lib.weak_deque)` across all three Classes. The use of native Python C-backed `extend` and `extendleft` makes merging vastly faster than iterating through objects individually

### Resolution & Retrieval

- **`resolve(KeyString: str) -> str`**: The core dictionary function. It linearly sweeps _only_ `bounded_strong` followed by `bounded_weak`. It executes Left/Right accumulation geometry, applies regex substitutions (`re.sub()`) if the matched Definition is a pattern, stops searching if a Base strike occurs, and returns the concatenated Raw Text.
- **Pattern Getters**: Because the deques are pre-sorted by Class, fetching patterns is highly optimized.
    - **`get_active_pre_patterns()` / `get_active_post_patterns()`**: Returns a combined, ordered list of all Strong and Weak patterns for the specified class, ready to be applied to a Payload or Literal String.
    - **`get_local_pre_patterns()` / `get_local_post_patterns()`**: Iterates from the outer edges of the respective deques inward until hitting the first `None` sentinel, returning only the patterns registered in the most-recent execution scope.

## Architectural Design Decisions

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
