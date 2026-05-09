# Core Data Types and Subsystem Interfaces

This document defines the shared data structures and contracts between the processing subsystems.

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

## Token Class (Lexer -> Parser interface)

**Purpose:** Represents an atomic unit identified by the character-by-character pushdown automaton.

### Token Fields

- `content` (str): Unprocessed token content (includes internal boundary markers if applicable).
- `position` (int): Character offset of the start marker in the input string. TBD: maybe delete if unused?
- `length` (int): Number of characters consumed. TBD: maybe delete if unused?
- `token_type` (`TokenType` Enum) is one of:
    - `'TEXT'`: Basic plain text; no internal parsing required. Local Pre-Patterns still apply.
    - `'LAZY_DEF'` and `'EAGER_DEF'`: Defines a key/pattern to a replacement value, starting `:` and `::` respectively.
        - Formerly `'DEFINITION'`
    - `'ARGUMENT'`: If in invocation mode, a leading-`:` Segment string without Definition syntax.
    - `'INVOCATION'`: A bounded token (`<...>`) intended to be Resolved against Definitions. The Lexer does not identify Positional Invocations vs normal, nor Scoped vs Unscoped. That must be handled by the Parser. All variations will simply produce base INVOCATION Tokens.
        - Escape Block syntax (`</.../>`) will also become an `INVOCATION` Token, but will later be identified by the Parser.
    - `'SCOPE'`: A bounded substring (`{...}`) intended to trigger PRNG Option Selection or isolate the contents.
    - `'SPLIT'`: A zero-depth divider (`|`) separating PRNG options.
    - `'MODIFIER'`: Math/Quantity rules (e.g., `2$$`) prepended to Invocation Segments or `|`-divided Raw Text Scope Node Payloads.

### Token Invariants

- `SPLIT` and `MODIFIER` tokens are only identified at the current lexical depth (zero-depth relative to the parent string). Nested markers remain inert text.
- Escape characters preceding genericized syntax markers are passed through to the Parser.
- TODO Later: The Lexer identifies token types dynamically based on a global `SyntaxConfig` object.

## Definition Class

**Purpose:** Parsed directive from a Definition token, ready for Context Stack insertion.

### Syntax Matrix and Default Characters

Definitions consist of a 4D orthogonal syntax matrix, detailed in `ARCHITECTURE_MANIFESTO.md`. Briefly `[Timing][Class]KeyPattern[Position][Strength]ValuePattern`, options as follows:
- **Timing:** `:` -> Lazy Evaluation; `::` -> Eager Evaluation
- **Class:** _Empty_ -> Bounded Macro; `<` -> Unbounded Pre-Pattern; `>` -> Unbounded Post-Pattern
- **Position:** _Empty_ -> Base Replacement `<` -> Left-Concat; `>` -> Right-Concat
- **Strength:** `:` -> Strong; `::` -> Weak

### Definition Fields

- `pattern_class` (str): `'PRE'`, `'BOUNDED'`, or `'POST'`.
- `direction` (str):
    - `'BASE'`: Search-terminating root value.
    - `'LEFT'`: Prepended to the base/match.
    - `'RIGHT'`: Appended to the base/match.
- `key_is_regex` (bool): Key used `/ /` delimiters.
- `value_is_regex` (bool): Value used `/ /` delimiters.
- `key` (str): Pattern or identifier to match (delimiters stripped).
- `value` (str): Replacement text or format string (delimiters stripped).
Both Strength and Timing are instructions to the Parser, not part of the state information of the Definition, so they are not saved as fields.

### Definition Invariants

- `key` and `value` have bounding syntax and escape characters stripped where appropriate.

## DefLibrary (Definition Library) Class

Collection of Definition objects providing functional access. Fully defined in `DEFINITION_LIBRARY_SPECIFICATION.md`.

## ASTNode Class

**Purpose:** Represents a semantic unit for further processing. The Parser maps surviving zero-depth Tokens into specific subclasses of the polymorphic `ASTNode` base class.

### Base Interface

`ASTNode` superclass contains some generic fields and functions common to all Node types:
- `raw_text` (str): Original text payload before evaluation.
- TODO: other shared fields and functions
    - TBD: Maybe has a generic `process()` to trigger internal logic that has varying output, maybe optional implementation of `expand()` and/or `execute()`?

### Node Subclasses

Each Node subclass represents a specific type of user input and has its own specific internal logic, generally built as a subset of a common overall processing pipeline.
- `TextNode`: Contains Raw text.
- `ScopeNode`: Contains a Raw Payload that may be `|`-Split with a single optional `Modifier` (e.g., `2$$`). Controls Scope Boundaries.
- `UnscopedInvocationNode`: Contains `|`-Split Segments, each an optional `Modifier`. Key-String Segments are Evaluated preceding Context Stack lookup, with the Parsed Definitions and Nodes returned to the Parent.
- `ScopedInvocationNode`: Contains `|`-Split Segments, each an optional `Modifier`. Key-String Segments are Evaluated preceding Context Stack lookup, with the resulting Raw Texts subsequently Evaluated and returned as Literal Text.
- `PositionalNode`: Single `<>`-bounded digit used to reference the Segments of the Parent Invocation rather than the Library of explicit Definitions.
- `EscapeNode`: Contains already-Evaluated or other Literal text not intended to go through the full engine process. Processes Unicode escape sequences as well.

### Node Invariants

- Inner boundaries in the content strings of Nodes are stored as raw strings; they are not parsed into child trees on creation.

## Context Class

**Purpose:** The Context is a single mutable object containing the full engine state that is passed up and down between various Nodes and functions. It holds the Library of explicit Definitions, the array of implicit Positional Values (TBD as strings, Definitions, or other), the PRNG Seed with its iteration behavior, the Trace object (TODO) that records Selection information, and a global TTL or timeout (or other mechanism) to prevent infinite processing.

**Architecture:**

- DefLibrary
- Positional string array: Stores Literal Texts from next-highest Invocation Segments for retrieval by Positional Invocations
    - TODO: Array of strings or Definition objects?
- PRNG: Implements path-hashed seed tracking (eg `parent_seed + child_index`) for deterministic sibling generation.
- Trace object: TODO explain Trace
- Global TTL Integer?

---

## Subsystem Contracts & Promises

### Lexer Contract

TODO Integrate or insert Selection into this transition
What the Lexer guarantees:

1. **No Lookahead Ambiguity:** Processing relies strictly on stateful index tracking, never complex regex lookaheads.
2. **Lossless Reconstruction:** Tokens correspond 1:1 with the input. Concatenating the raw text fields of the output tokens will result in an exact, byte-for-byte duplicate of the input string.
3. **Lazy Isolation:** All—and only—top-level (zero-depth) syntax markers are identified as discrete or bounded tokens. Everything else is guaranteed to be a TEXT token.
4. **Data Offloading:** The Lexer outputs strongly typed, clean Token objects. It does not attempt to parse definitions into key/value pairs, instantiate AST Nodes, differentiate Invocation variants, or interpret modifiers.
5. TODO Something about Invocation-mode flag for changing Definition-Split priority interaction.

### Parser Contract

What the Parser guarantees:

1. The Parser interprets the Tokenized strings into code Objects with semantic meanings. It does not apply string transformation logic or recursion by itself.
2. **Polymorphic Processing:** Processing (eg Expansion, Execution) logic is entirely encapsulated within the methods of the AST subclasses, eliminating procedural type-checking.
3. **Explicit Intent:** The Parser distinguishes Invocation intents immediately, outputting explicit `ScopedInvocationNode`, `UnscopedInvocationNode`, or `PositionalNode` objects (in addition to the non-Invocation objects).
4. **Selective Escape Stripping:** The Parser strictly strips escape characters (`\`) _only_ when they precede custom structural syntax markers (ie the input intent is for the character to be understood as just the character, not the escape character, but in a different type of object than the input string with just the unescaped character would have produced). It preserves all standard text escapes (eg `\n`, `\t`, `\d`) as literal strings, leaving them fully intact for downstream regex compilation or escape decoding. TODO should we strip escaped backslash `\\` to a single backslash, or would that just wastefully force a user to use 4x backslashes to, for example, get a single backslash in a Regex Pattern; should we use a different escape character to not overlap, eg tick '`'?
5. TODO Evaluates Eager Definitions
6. TODO Adds definitions to provided DefLibrary or defaults to Context.DefLibrary.

### DefLibrary Contract

1. Maintains proper ordering when using inbuilt merging function(s).
2. TODO Something about Resolution functionality and/or Resolved Value.

### Node Contract

1. If Scoped, removes (relevant, eg not TTL) changes from the Context DefLibrary and PRNG Seed.
---

## Related Documentation

- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing details
- [DEFINITION_LIBRARY_SPECIFICATION.md](DEFINITION_LIBRARY_SPECIFICATION.md) - Definition Library object
- [ARCHITECTURE_MANIFESTO.md](ARCHITECTURE_MANIFESTO.md) - Overall engine operation and paradigms
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
