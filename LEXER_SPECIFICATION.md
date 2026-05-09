# Lexer Specification

This document defines the lexical analysis subsystem: the character-by-character processing pipeline that converts raw input strings into List, segmented into sub-Lists, of zero-depth semantic Tokens.

## 1. System Overview

The Lexer operates strictly under the Breadth-Eager, Depth-Lazy paradigm. It is entirely blind to text transformation logic and random seed generation; its sole responsibility is to identify top-level structural boundaries and Segment split markers, then slice the input text into labelled chunks.

To bypass the catastrophic performance penalties of Python string buffering, the Lexer utilizes an **Interval-Tracking Speculative Architecture**, ensuring $O(N)$ linear time complexity in a single string sweep, followed by lightweight array culling.

## 2. Input & Output Signatures

**Input:**

1. A raw text string.
2. `is_invocation` (Boolean, default `False`): A flag indicating the text is the isolated interior of an Invocation, modifying some behaviors slightly to support streamlined UX.

**Output:** `List[List[Token]]`

- The Lexer _always_ returns a list of Segments (which are themselves lists of Tokens). If no valid Segment dividers (`|`) exist, it simply returns a single-item outer list containing the lexed Tokens (e.g., `[[Token_1, Token_2]]`).

## 3. Core Lexing Architecture

### 3.1 The FSM Strategy & Index Optimization

Instead of slicing and buffering strings character-by-character, the Lexer runs a single pass over the text using a Finite State Machine (FSM) approach. It tracks structural edges (opens/closes) in pre-sorted integer arrays (bins) for each boundary pair/type (i.e., per output Token Type).

- **The Negative Trick:** To avoid the overhead of instantiating tuple objects (e.g., `(5, 'open')`), the Lexer uses signed integers within a single array. Positive integers represent opening boundaries, and negative integers represent closing boundaries.
- **0-Based Indexing:** Standard 0-based indexing is preserved. An opening marker at the first character is `0`. A theoretical closing marker at index `0` would be immediately discarded by the stack logic as "unmatched" before ever being recorded, meaning a mathematically ambiguous `-0` state never enters the candidate arrays.
    - If later engine features implicate zero-length Tokens, this concept may have to be revisited, but the rule of a Token always corresponding to at least one input character is currently absolute.
- **Half-Open Intervals:** All matched boundaries and discrete markers resolve to half-open intervals: `[start, end)`.
- This natively maps to Python's C-backed slicing (e.g., `text[start:end]`), eliminating the need for `+1` mathematical offsets during the payload generation loop.
    - Note that per the above **Negative Trick**, the negative `end` indices are taken as their absolute values, not a count-from-end index.
- **Discrete Tokens:** Zero-depth discrete tokens like the Segment divider (`|`) are recorded as 1-long half-open intervals. For example, a pipe at index `5` is recorded as `[5, 6]`.

### 3.2 Invocation-Mode Subsystem Rules

When `is_invocation_payload=True`, the Lexer applies these internal state shifts:

1. **Priority Inversion:** The Rigidity Hierarchy (Section 4) swaps the priority of Segments (`|`) and standard (EOL/`|` terminated) Definitions to preserve Segment divisions in Invocation Payloads.
2. **Argument Token Emission:** If a segment-leading colon `:` fails to form a complete Definition interval, the orphaned syntax is emitted as `TokenType.ARGUMENT` rather than degrading to `TokenType.TEXT`.
3. **Definition Boundary Character:** The character preceding the start or at the end of a Definition (in addition to start/end of input), `def_boundary`, is changed from `\n` in Standard Mode to `|` in Invocation Mode.

### 3.3 Modifier Extraction

Modifiers (`$$`) are extracted from the boundaries of valid Segments in _both_ modes. The Lexer scans from the start of each resolved segment up to the last `$$` marker, stripping it from the payload and emitting it as a Modifier Token. Interpretation of multiple modifiers is deferred to the Parser.

### 3.4 Token Emission & String Views

The Lexer does not directly slice or copy text. It acts as a geometric surveyor returning a map of boundaries, not the actual boundary contents. All emitted Tokens are "String Views" containing a reference to the original, immutable `root_string` and their spatial integer coordinates (`start`, `end`, and optionally `separator_idx`). String memory allocation is deferred until the string object itself is needed.

### 3.5 Selective Escape Stripping

To avoid the "Slash Collision Trap" (destroying file paths or standard regex inputs), the Lexer employs selective escaping using the backslash (`\`).

- A backslash only acts as an escape character if it immediately precedes a custom structural syntax marker used by the engine (e.g., `\<`, `\:`, but not newlines).
- If escaped, the Lexer ignores the marker for boundary tracking, but does not modify the base text.
- **Standard escapes (e.g., `\n`, `\t`, `\C:\`) are treated as pure literal text** and are not processed or stripped by the Lexer.

## 4. The Rigidity Hierarchy & Interval Culling

TODO: Validate the following WRT structural hierarchy.

To inherently protect nested syntax and isolate user typos (unbalanced brackets), the Lexer applies a **Deferred-Priority, Zero-Depth Culling Algorithm**. Candidate intervals are evaluated against each other based first on strict structural hierarchy, then with a set priority order to resolve nesting conflicts. A candidate interval that falls strictly within another candidate interval will be consumed as raw text contents of the outer interval. If a softer boundary falls strictly inside a harder boundary, the softer boundary is destroyed (treated as raw text).

Crucially, the relationship between Segments (`|`) and standard (i.e. EOL) Definitions (`: \n`) changes fundamentally depending on the Payload context. The `is_invocation_payload` flag dynamically swaps their priority. In standard text, Definitions naturally consume Segments to allow for multi-option values (e.g., `:Key:A|B\n`). Therefore, EOL Definitions are harder than Segments. Inside an Invocation, Segments act as hard dividing walls for Keys, Definitions, and Arguments. A Definition cannot bleed across options (e.g., `<Macro|:Key:A|B>` is a Key, Definition, and Argument, not a Key and Multi-Option Definition). Therefore, Segments are harder than standard (non Multi-Line) Definitions.

The hierarchy, from hardest to softest, for **standard text** is:

1. **Multi-Line Definitions (`: :<< >>`)**
    - Consumes everything, including newlines.
2. **Scopes (`{ }`)**
3. **Invocations (`< >`)**
4. **Standard EOL Definitions (`: : \n`)**
    - Encompasses both Lazy and Eager Definitions, which will be divided later. Terminates at the end of the line. Safely encapsulates any `|` characters within its bounds.
5. **Segments (`|`)**
    - Divides text into Segments if outside a Definition, Scope, or Invocation.
6. **Modifiers (`$$`)**

For **Invocation Payloads (`is_invocation_payload = True`)**, the order is:

1. **Multi-Line Definitions (`: :<< >>`)**
2. **Scopes (`{ }`)**
3. **Invocations (`< >`)**
4. **Segments (`|`)**
    - Above standard Definitions, not consumed by them.
5. **Standard Definitions and Arguments (`: |`)**
6. **Modifiers (`$$`)**

## 5. Token Generation

After the culling process finalizes the array of top-level intervals:

1. The Lexer iterates over the intervals.
2. Literal text between intervals is captured as `TokenType.TEXT`.
3. The bounded intervals are mapped to their respective `TokenType` enums (e.g., `INVOCATION`, `SCOPE`, etc.).
4. The final flat list of Tokens is split along any `TokenType.SPLIT` (`|`) tokens, assembling the final `List[List[Token]]` to be returned to the Parser.

## 6. TODO Definition Algorithm

- TODO: Describe how the interval merging and nested consumption works.
- TODO: the exact methodology of shadowing or culling lower priorities is TBD. Could be a separate shadow index Set or interval-List, or could be an operation to modify the lower bins directly.

### Pushdown Automata Algorithm

After the initial string scan, all (unescaped) potential start and end indices for each particular class/priority of Token will be in a single array/List "bin", with the end indices negated but ordered by their true position, that is pre-sorted by nature of its generation. At the time a bin is processed, the necessary shadowing from earlier priorities has already been actioned, so the only interactions that need to be handled are when an earlier interval is completely enclosed and consumed.

The Lexer iterates over these indices in the bin. As stated, an entry at index 0 will always be interpreted as a start index. During each pass, it keeps a stack of start indices, a list of top-level intervals, and a single "current" pending interval. When an available/unshadowed start (positive) index is encountered, it is pushed onto the stack. When an end index (negative) is encountered, the top start index is popped off the stack and joined to the end index to replace/create the pending interval. When there is no unmatched start index (or hitting a new start from an empty stack) or the end of the index list is hit, the pending interval is moved to the top-level list, and any remaining unmatched starts are dropped.

### Newline Interval Interruption

Only the intervals for Multi-Line Definition Blocks may span a newline `\n`, and standard EOL Definitions may capture their terminating newline, but all other intervals may not contain it. If the Pushdown Automata crosses a newline with unmatched indices in the stack, it triggers the same stack dump and save-pending-interval behavior as the end of list.

### Quasi-Definition Special Procedure

- TODO need to double-check exactly how the starts of multi-line Definition blocks are validated now. Don't have the same in-scan logic any more (though maybe it should have something?)
  The Definition utilizes the same automaton sweep to classify Quasi-Definition Interval Candidates as either Eager or Lazy and as a Definition or Argument. It does this by saving the indices of all unescaped `:` during the initial string scan, then checking the character preceding the saved indices during the index list sweep. Because the only way to trigger a Definition start would also end a preceding (non-multi-line) Definition, they cannot nest themselves without being consumed/shadowed by a harder interval.

**Start Validation:** Iterate forward. A positive integer is a valid `start_idx` ONLY if it satisfies the **Leading Constraint**: `idx == 0` or `text[idx - 1] == def_boundary` (where `def_boundary` is `\n` in Standard Mode, or `|` in Invocation Mode).

**The Forward Walk:** Once a valid `start_idx` is locked, continue walking forward in the array:

- _Positive Number (Colon):_
    - If `value == start_idx + 1`, flag `is_eager = True`.
    - Otherwise, flag `has_separator = True` and record `separator_idx = value`. (Ignore any further positive integers).
- _Negative Number (Terminator):_ This establishes `end_idx = abs(value)`. The interval `[start_idx, end_idx)` is closed and the flags can be checked to determine the type:
    - **If `has_separator == True`:** The syntax is a valid Definition. Cast its zero-depth shadow. Emit `DEFINITION_EAGER` or `DEFINITION_LAZY` based on `is_eager` and pass the `separator_idx` into the Token.
    - **If `has_separator == False`:** The interval was not a Definition, but may be an Argument depending on the calling Invocation mode.
        - _Standard Mode:_ Discard the interval. It casts no shadow. It degrades to raw text.
        - _Invocation Mode:_ Lock the interval and cast its shadow. Emit `ARGUMENT_EAGER` or `ARGUMENT_LAZY` (no `separator_idx` passed).

### The Multi-Line Value Wrapper (`<< ... >>`)

TODO: Review this section WRT the new scan-sweep algorithm
To support "Container Macros" and multi-line values, the Lexer supports explicit block boundaries that override the EOL termination rule.

- **The Mode-Switch Rule:** The opening wrapper (`<<`) must immediately follow the Definition's strength marker on the _same line_. If found, EOL termination is suspended.
- **The Nested Block Trap:** The Lexer cannot just blindly scan for the first `>>`. Because blocks can contain other blocks, the Lexer treats `<<` and `>>` as a paired pushdown-automaton boundary like other boundary markers. It only closes the block when the outermost `>>` is reached.
- **Strict Newline Capture:** The Lexer does _not_ chomp newlines, it simply captures them in the Definition Token as needed. Leading, trailing, and internal newlines inside the `<< >>` block are preserved perfectly, granting the user explicit control over text flow.

## OLD Lexer Specification

This document defines the lexical analysis subsystem: the character-by-character processing pipeline that converts raw input strings into a flat, zero-depth `Token` list.

## 1\. System Overview

The Lexer performs the first stage of the Macro Engine pipeline:

```text
Raw Input String → [LEXER] → Token List
```

The Lexer operates strictly under the **Breadth-Eager, Depth-Lazy** paradigm. It is entirely blind to execution logic, random seed generation, or contextual state. Its sole responsibility is to identify top-level structural boundaries and safely encapsulate nested syntax as inert text.

To bypass the catastrophic performance penalties of Python string buffering, the Lexer utilizes an **Interval-Tracking Speculative Architecture**, ensuring O(N) linear time complexity.

---

## 2. Core Lexing Architecture

TODO still needs updating from LLM.

To support Order-Independent Evaluation and Graceful Degradation without the catastrophic backtracking penalties of Context-Free Grammars, the Lexer utilizes a **Priority-Stratified Pass Resolution** algorithm. It functions as a pure, stateless string processor, optionally accepting an `is_invocation` flag to activate Segment-aware boundary rules.

The lexing pipeline is broken into four distinct computational phases:

### Phase 1: The O(N) Structural Sweep (Blind Discovery)

The Lexer does not attempt to pair boundaries during its initial string traversal. Instead, it performs a single, rapid sweep of the text, looking strictly for configured structural characters (`<`, `>`, `{`, `}`, `:`, `|`, `\n`).

- **Inline Escapes:** If a structural character is immediately preceded by a backslash (e.g., `\|`), the Lexer ignores it. It does not record the index, leaving the literal `\|` sequence in the text payload for downstream unescaping.
- **The Linked List:** Valid structural hits are recorded into a Doubly-Linked List of `Edge` objects, storing their character type and original integer index.

### Phase 2: Priority-Stratified Resolution (The Rigidity Hierarchy)

Instead of processing the Edge list linearly from left-to-right, the Lexer traverses the list multiple times, resolving pairs based on a strict "Rigidity Hierarchy" (Hardest boundaries to Softest boundaries). For each pass, only the highest-level matched pairs of that type are recorded.

1. Scopes `{ }`
2. Invocations `< >`
3. Multi-Line Definitions `<< >>`
4. EOL Definitions `: \n`
5. Segments `|`

_If `is_invocation=True`, then the order of EOL Definitions and Segments is swapped, so `|` will break up a Definition._

**The Gap-Jumping Subsumption Rule (Zero-Depth Culling):**
When a pass successfully pairs an opening and closing marker, it updates the pointers of the Linked List to "jump" the gap between them.

- _Example:_ If Priority 1 pairs `{` at index 5 and `}` at index 20, the node before index 5 is linked directly to the node after index 20.
- _Result:_ Any structural hits trapped inside `[5, 20]` are instantly orphaned in memory. They become physically invisible to all subsequent, lower-priority passes, natively enforcing the Depth-Lazy axiom.

**The Newline Stack Wiper:**
Scopes and Invocations are explicitly forbidden from natively spanning newlines. During Pass 1 and Pass 3, if the traversal encounters a `\n` hit, it instantly empties its active "looking for a close" stack. Unmatched open markers fall back to literal text.

### Phase 3: Slicing and Tokenization

Once all Priority Passes are complete, the surviving, fully-paired intervals in the Linked List represent the true, zero-depth structural boundaries of the string.
The Lexer iterates through these final intervals and the original string to emit Tokens:

- **Bounded Syntax:** The string slice _inside_ a matched interval is captured (including its markers) and cast to the appropriate Token (`TokenType.INVOCATION`, `TokenType.SCOPE`, `TokenType.DEFINITION`).
- **Raw Interstitial Text:** Any string indices falling _between_ the matched zero-depth intervals are sliced out and cast to `TokenType.TEXT`.
- **Degradation:** Any structural hits that failed to pair (e.g., an orphaned `<` or `:`) naturally fall into the interstitial gaps and are gracefully absorbed into `TokenType.TEXT`.

### Phase 4: Segment Routing

Because the fundamental relationship between `|` and Definitions changes depending on context, the Lexer dynamically routes the final Tokens:

- **Standard Text (`is_invocation=False`):** The `|` character is treated as meaningless text. The Lexer returns a single `List[Token]`.
- **Invocation Payloads (`is_invocation=True`):** The `|` character acts as a hard boundary (Priority 4). It physically severs the linked list into sublists, preventing Priority 5 (EOL Definitions) from bleeding across options. The Lexer slices the original string at these `|` intervals and returns a `List[List[Token]]`, representing a cleanly separated array of Segments ready for the AST.

---

## 3\. Token Configuration & State

### 3.1 Dynamic Syntax Injection

TODO: The Lexer does not hardcode its boundary markers. It receives a `SyntaxConfig` object at runtime mapping characters to a `TokenType` Enum.

**Supported Token Types:**

- `TEXT`: Plain text, not containing any other syntax. No inherently implied Raw or Literal nature.
- `DEFINITION`: Bounded macro, pre-pattern, or post-pattern rules.
- `INVOCATION`: Definition lookup wrappers (`< >`).
- `SCOPE`: Atomic text wrappers (`{ }`).
- `SPLIT`: Zero-depth option dividers (`|`).
- `MODIFIER`: Selection/Quantity rules (`2$$`).

---

## 4\. Escape Sequences & Formatting

### 4.1 Selective Escape Stripping

To avoid the "Slash Collision Trap" (destroying file paths or standard regex inputs), the Lexer employs selective escaping using the backslash (`\`).

- A backslash only acts as an escape character if it immediately precedes a custom structural syntax marker defined in the `SyntaxConfig` (e.g., `\<`, `\:`).
- If escaped, the Lexer ignores the marker for boundary tracking, but does not modify the base text.
- **Standard escapes (e.g., `\n`, `\t`, `\C:\`) are treated as pure literal text** and are not processed or stripped by the Lexer.

---

## 5\. Definition Boundary Rules

The Lexer handles macro definitions (`:key:value`) using a dual-mode termination strategy to safely isolate values.

### 5.1 End-of-Line (EOL) Termination (Default)

By default, when the Lexer encounters a zero-depth definition header, it tracks the value string until it hits a newline character (`\n`) or the end of the string.

### 5.2 The Multi-Line Value Wrapper (`<< ... >>`)

To support "Container Macros" and multi-line values, the Lexer supports explicit block boundaries that override the EOL termination rule.

- **The Mode-Switch Rule:** The opening wrapper (`<<`) must immediately follow the definition's strength marker on the _same line_. If found, EOL termination is suspended.
- **The Nested Block Trap:** The Lexer cannot just blindly scan for the first `>>`. Because blocks can contain other blocks, the Lexer treats `<<` and `>>` as a paired pushdown-automaton boundary like other boundary markers. It only closes the block when the outermost `>>` is reached.
- **Strict Newline Capture:** The Lexer does _not_ chomp newlines, it simply captures them in the Definition Token as needed. Leading, trailing, and internal newlines inside the `<< >>` block are preserved perfectly, granting the user explicit control over text flow.
