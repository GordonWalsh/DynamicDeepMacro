# Core Data Types and Subsystem Interfaces

This document defines the shared data structures and contracts between the three processing subsystems: Lexer, Parser, and Evaluator.

## Overview

The macro engine processes text through a strictly lazy, recursive lifecycle:

```
String Input
↓ [LEXER]
Token List
↓ [PARSER]
Abstract Syntax Tree (AST) with Local Definitions
↓ [EVALUATOR + Calling Context]
Final String Output
```
This document specifies the data structures passed between stages and the invariants guaranteed by each subsystem.

### Token Class (Lexer -> Parser interface)

**Purpose:** Represents an atomic unit identified by the character-by-character pushdown automaton. 

**Fields:**
- `value` (str): Unprocessed token content (includes internal boundary markers if applicable).
- `position` (int): Character offset of the start marker in the input string.
- `length` (int): Number of characters consumed.
- `type_markers` (`Tuple[str, str, str]`): Tuple defining `(Token_Type, Start_Marker, End_Marker)`. 
  `Token_Type` is one of:
  - `'LITERAL'`: Basic plain text; no internal parsing required.
  - `'DEFINITION'`: Defines a key/pattern to a replacement value (`:`, `:<`, `:>`, etc.).
  - `'INVOCATION'`: A bounded token (`< >`) intended to be resolved against the Context Stack.
  - `'MULTI_VALUE'`: A bounded substring (`{ }`) intended to trigger PRNG reduction.
  - `'SPLIT'`: A zero-depth divider (`|`) separating PRNG options.
  - `'MODIFIER'`: Math/Quantity rules (e.g., `2$$`) prepended to Invocations or Multi-Value groups.

**Invariants:**
- `SPLIT` and `MODIFIER` tokens are only identified at the current lexical depth (zero-depth relative to the parent string). Nested markers remain inert text.
- Escape characters preceding genericized syntax markers are passed through to the Parser.

### Definition Class (Parser Output)

**Purpose:** Parsed directive from a Definition token, ready for Context Stack insertion.

**Syntax Matrix:**
- **Start Markers (Class):** `:` (Bounded Macro), `:<` (Pre-Pattern), `:>` (Post-Pattern).
- **Middle Markers (Direction/Strength):** `[Empty String]` (Base), `<` (Left-Concat), `>` (Right-Concat); then `:` (Strong) or `::` (Weak).

**Fields:**
- `pattern_class` (str): `'PRE'`, `'BOUNDED'`, or `'POST'`.
- `direction` (str): 
  - `'BASE'`: Search-terminating root value.
  - `'LEFT'`: Prepended to the base/match.
  - `'RIGHT'`: Appended to the base/match.
- `strength` (str): `'STRONG'` (Stack HEAD) or `'WEAK'` (Stack TAIL).
- `key_is_regex` (bool): Key uses `/ /` delimiters.
- `value_is_regex` (bool): Value uses `/ /` delimiters.
- `key` (str): Pattern or identifier to match (delimiters stripped).
- `value` (str): Replacement text or format string (delimiters stripped).

**Invariants:**
- `key` and `value` have bounding syntax and escape characters stripped where appropriate.

### ASTNode Class Hierarchy (Parser Output)

**Purpose:** Represents a semantic, executable unit for evaluation. The Parser maps surviving zero-depth Tokens into specific subclasses of the polymorphic `ASTNode` base class.

**Base Interface (`ASTNode`):**
- `raw_text` (str): Original text payload before evaluation.
- `evaluate(context: MacroContext) -> str`: The polymorphic execution contract.

**Subclasses:**
- `LiteralNode`: Contains static text. Evaluation applies Pre/Post patterns and returns the string.
- `MultiValueNode`: Contains a raw payload and an optional `modifier` (e.g., `2$$`). Evaluation triggers PRNG list reduction.
- `InvocationNode`: Contains a `key` and an optional `modifier`. Evaluation triggers Context Stack lookup, followed by PRNG list reduction on the retrieved string.
- `BlockNode`: The container for a scoped text area (e.g., the global prompt or a Transparent Block).
  - `is_transparent` (bool): If True, scoped definitions leak to siblings.
  - `local_definitions` (List[Definition]): Parsed definitions extracted from the scope (Scope Hoisting).
  - `outputs` (List[ASTNode]): The sequence of polymorphic child nodes to be evaluated.

**Invariants:**
- `outputs` contains strictly `ASTNode` objects, never raw `Token` objects.
- Inner boundaries of `InvocationNode` and `MultiValueNode` are stored as raw strings; they are not parsed into child trees until `.evaluate()` is explicitly called.

### MacroContext Class (Evaluator State)

**Purpose:** State container managing the PRNG and lexically scoped definitions.

**Architecture:**
- Deque-based: Strong definitions pushed to HEAD, Weak definitions pushed to TAIL.
- PRNG: Implements path-hashed seed tracking (`parent_seed + child_index`) for deterministic sibling generation.

**Methods:**
- `push(definitions: List[Definition]) → None`: Inserts definitions into the deque.
- `get_definitions(key: str) → Tuple[Optional[Definition], List[Definition]]`: Traverses the deque Left-to-Right. Accumulates `LEFT` and `RIGHT` modifiers into a list. Terminates search and returns `(Base_Definition, Modifiers_List)` upon hitting a `BASE`.
- `get_unbounded_patterns(pattern_class: str) → List[Definition]`: Returns discrete `PRE` or `POST` patterns in priority order.

**Invariants:**
- The Context Stack acts strictly as a search engine. It never evaluates an AST node or provides default/fallback macro rules.

---

## Subsystem Promises

### Lexer Promises (String → Token List)
1. **No Lookahead Ambiguity:** Character-by-character processing.
2. **Lossless:** Tokens correspond 1:1 with boundary rules; concatenating raw token values reconstructs the exact input.
3. **Lazy Isolation:** All and only top-level (zero-depth) SPLIT and MODIFIER markers are identified as discrete tokens.

#### Parser Promises (Token List → ASTNode)
1. **State/Data Decoupling:** Separates `DEFINITION` tokens from execution tokens.
2. **Object Instantiation:** Parses raw definition strings into strongly typed `Definition` objects.
3. **Polymorphic Mapping (Breadth Eagerness):** Maps the remaining zero-depth execution tokens into their corresponding `ASTNode` subclasses (e.g., `LiteralNode`, `InvocationNode`).
4. **Depth Laziness:** Never lexes or parses the internal string contents of an `INVOCATION` or `MULTI_VALUE` token.

#### Evaluator Promises (ASTNode + Context → String)
1. **The Gatekeeper (List Reduction):** Intercepts raw payload strings, Lexes them, and applies `SPLIT`/`MODIFIER` reduction *before* passing the winning sub-list to the Parser. Unselected PRNG branches are instantly destroyed.
2. **Polymorphic Execution:** Execution logic is entirely encapsulated within the `.evaluate()` methods of the AST subclasses, eliminating procedural type-checking.
3. **Ephemeral Instantiation:** Child AST branches generated during macro expansion or Multi-Value selection are instantiated dynamically, evaluated, and immediately garbage-collected.
---

## Related Documentation

- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing details
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Token → AST parsing details
- [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String evaluation details
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
