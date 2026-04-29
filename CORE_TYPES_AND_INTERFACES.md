# Core Data Types and Subsystem Interfaces

This document defines the shared data structures and contracts between the three processing subsystems: Lexer, Parser, and Evaluator.

## Overview

The macro engine processes text through a lazy, recursive lifecycle, roughly:

```text
String Input
↓ [Lexing and Segmenting]
List of Token Lists
↓ [Invocation and/or Selection]
Single Flat List of Tokens
↓ [Parsing and Expansion]
Abstract Syntax Tree (AST) with Local Definitions
↓ [Execution]
Final String Output
```

This document specifies the data structures passed between stages and the invariants guaranteed by each subsystem.

### Token Class (Lexer -> Parser interface)

**Purpose:** Represents an atomic unit identified by the character-by-character pushdown automaton.

**Fields:**

- `content` (str): Unprocessed token content (includes internal boundary markers if applicable).
- `position` (int): Character offset of the start marker in the input string.
- `length` (int): Number of characters consumed.
- `token_type` (`TokenType` Enum) is one of:
    - `'TEXT'`: Basic plain text; no internal parsing required. Local Pre-Patterns still apply.
    - `'DEFINITION'`: Defines a key/pattern to a replacement value (`:`, `:<`, `:>`, etc.).
    - `INVOCATION`: A bounded token (`< >`) intended to be Resolved against Definitions. The Lexer does not identify Positional Invocations vs normal, nor Scoped vs Unscoped. That must be handled by the Parser. All variations will simply produce base INVOCATION Tokens.
    - `'SCOPE'`: A bounded substring (`{ }`) intended to trigger PRNG Option Selection or isolate the contents.
    - `'SPLIT'`: A zero-depth divider (`|`) separating PRNG options.
    - `'MODIFIER'`: Math/Quantity rules (e.g., `2$$`) prepended to Invocation Segments or `|`-divided Raw Text Scope Node Payloads.

**Invariants:**

- `SPLIT` and `MODIFIER` tokens are only identified at the current lexical depth (zero-depth relative to the parent string). Nested markers remain inert text.
- Escape characters preceding genericized syntax markers are passed through to the Parser.
- TODO Later: The Lexer identifies token types dynamically based on a global `SyntaxConfig` object.

### Definition Class (Parser Output)

**Purpose:** Parsed directive from a Definition token, ready for Context Stack insertion.

**Syntax Matrix and Default Characters:**

- **Start Markers (Class):** `:` (Bounded Macro), `:<` (Pre-Pattern), `:>` (Post-Pattern).
- **Middle Markers (Direction/Strength):** `[Empty String]` (Base), `<` (Left-Concat), `>` (Right-Concat); then `:` (Strong) or `::` (Weak).

**Fields:**

- `pattern_class` (str): `'PRE'`, `'BOUNDED'`, or `'POST'`.
- `direction` (str):
    - `'BASE'`: Search-terminating root value.
    - `'LEFT'`: Prepended to the base/match.
    - `'RIGHT'`: Appended to the base/match.
- `strength` (str): `'STRONG'` (Stack HEAD) or `'WEAK'` (Stack TAIL). TODO this should be unneeded.
- `key_is_regex` (bool): Key uses `/ /` delimiters.
- `value_is_regex` (bool): Value uses `/ /` delimiters.
- `key` (str): Pattern or identifier to match (delimiters stripped).
- `value` (str): Replacement text or format string (delimiters stripped).

**Invariants:**

- `key` and `value` have bounding syntax and escape characters stripped where appropriate.

### ASTNode Class Hierarchy (Parser Output)

**Purpose:** Represents a semantic unit for further processing. The Parser maps surviving zero-depth Tokens into specific subclasses of the polymorphic `ASTNode` base class.

**Note on Parser Return Type:** The Parser does _not_ return a single root node. To avoid creating dummy wrappers, it returns a flat `Tuple[List[Definition], List[ASTNode]]`.

**Base Interface (`ASTNode`):**

- `raw_text` (str): Original text payload before evaluation.
- TODO: other shared fields and functions

**Subclasses:**

- `TextNode`: Contains Raw text.
- `ScopeNode`: Contains a Raw Payload that may be `|`-Split with a single optional `Modifier` (e.g., `2$$`). Controls Scope Boundaries.
- `UnscopedInvocationNode`: Contains `|`-Split Segments, each an optional `Modifier`. Key-String Segments are Evaluated preceding Context Stack lookup, with the Parsed Definitions and Nodes returned to the Parent.
- `ScopedInvocationNode`: Contains `|`-Split Segments, each an optional `Modifier`. Key-String Segments are Evaluated preceding Context Stack lookup, with the resulting Raw Texts subsequently Evaluated and returned as Literal Text.
- `PositionalNode`: TODO explain PositionalNode
- `EscapeNode`: Probably. TODO explain EscapeNode

**Invariants:**

- The Parser strictly returns `ASTNode` objects and Definitions, never raw `Token` objects, in its output list.
- Inner boundaries in the content strings of Nodes are stored as raw strings; they are not parsed into child trees on creation.

### MacroContext Class (Evaluator State)

**Purpose:** State container managing the PRNG and lexically scoped definitions.

**Architecture:**

- Deque-based: Strong definitions pushed to HEAD, Weak definitions pushed to TAIL.
- PRNG: Implements path-hashed seed tracking (eg `parent_seed + child_index`) for deterministic sibling generation.
- Trace object: TODO explain Trace
- Positional string array: Stores Literal Texts from next-highest Invocation Segments for retrieval by Positional Invocations

**Methods:**

TODO confirm these:

- `push(definitions: List[Definition]) → None`: Inserts definitions into the deque.
- `get_definitions(key: str) → Tuple[Optional[Definition], List[Definition]]`: Traverses the deque Left-to-Right. Accumulates `LEFT` and `RIGHT` modifiers into a list. Terminates search and returns `(Base_Definition, Modifiers_List)` upon hitting a `BASE`.
- `get_unbounded_patterns(pattern_class: str) → List[Definition]`: Returns discrete `PRE` or `POST` patterns in priority order.

**Invariants:**

- The Context Stack acts strictly as a search engine. It never evaluates an AST node or provides default/fallback macro rules.

---

## Subsystem Contracts & Promises

### Lexer Contract

TODO Integrate or insert Selection into this transition
What the Lexer guarantees:

1. **No Lookahead Ambiguity:** Processing relies strictly on stateful index tracking, never complex regex lookaheads.
2. **Lossless Reconstruction:** Tokens correspond 1:1 with the input. Concatenating the raw text fields of the output tokens will result in an exact, byte-for-byte duplicate of the input string.
3. **Lazy Isolation:** All—and only—top-level (zero-depth) syntax markers are identified as discrete or bounded tokens. Everything else is guaranteed to be a TEXT token.
4. **Data Offloading:** The Lexer outputs strongly typed, clean Token objects. It does not attempt to parse definitions into key/value pairs, instantiate AST Nodes, differentiate Invocation variants, or interpret modifiers.

### Parser Contract

What the Parser guarantees:

1. The Parser interprets the Tokenized strings into code Objects with semantic meanings. It does not apply string transformation logic or recursion by itself.
2. **Polymorphic Processing:** Processing (eg Expansion, Execution) logic is entirely encapsulated within the methods of the AST subclasses, eliminating procedural type-checking.
3. **Explicit Intent:** The Parser distinguishes Invocation intents immediately, outputting explicit `ScopedInvocationNode`, `UnscopedInvocationNode`, or `PositionalNode` objects (in addition to the non-Invocation objects).
4. **Selective Escape Stripping:** The Parser strictly strips escape characters (`\`) _only_ when they precede custom structural syntax markers (ie the input intent is for the character to be understood as just the character, not the escape character, but in a different type of object than the input string with just the unescaped character would have produced). It preserves all standard text escapes (eg `\n`, `\t`, `\d`) as literal strings, leaving them fully intact for downstream regex compilation or escape decoding. TODO should we strip escaped backslash `\\` to a single backslash, or would that just wastefully force a user to use 4x backslashes to, for example, get a single backslash in a Regex Pattern; should we use a different escape character to not overlap, eg tick '`'?

#### Evaluator Promises (ASTNode + Context → String)

TODO this section needs to be replaced with better Expansion and Execution sections

1. **Distinct Option Selection Timing:** Option Selection is handled dynamically based on the object type.
    - **ScopeNodes (Raw Text):** Perform Option Selection immediately after `LexAndSegment` to cull unselected branches before Parsing.
    - **InvocationNodes (Dictionary Queries):** Do _not_ cull Segments natively. They `LexAndSegment`, Resolve all Segments against the dictionary, and then apply Modifiers to the _Resolved Values_ individually to Select Options.
2. **Polymorphic Execution:** Execution logic is entirely encapsulated within the `.execute()` methods of the AST subclasses, eliminating procedural type-checking.
3. **Ephemeral Instantiation:** Child AST branches generated during macro expansion or Group selection are instantiated dynamically, evaluated, and immediately garbage-collected.

---

## Related Documentation

- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing details
- ~~[PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Token → AST parsing details~~
- ~~[EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String evaluation details~~
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
