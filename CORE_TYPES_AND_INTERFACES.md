# Core Data Types and Subsystem Interfaces

This document defines the shared data structures and contracts between the three processing subsystems: Lexer, Parser, and Evaluator.

## Overview

The macro engine processes text through three sequential stages:

```
String Input
    ↓ [LEXER]
Token List
    ↓ [PARSER]
Abstract Syntax Tree (AST) with Definitions
    ↓ [EVALUATOR + Calling Context]
Final String Output
```
TODO objects are defined in `core_engine.py`, ensure consistency.
This document specifies the data structures passed between stages and the invariants guaranteed by each subsystem.

### Token Class (Lexer -> Parser interface)

**Purpose:** Represents an atomic unit identified by the character-by-character lexing process.

**Fields:**
- `value` (str): Unprocessed token content
- `position` (int): Character offset in input string
- `length` (int): Number of characters consumed
TODO is length or endpoint better?
- `type_markers` (`Tuple[(str, str, str)]`) Type of object token corresponds to, boundary marker characters, start and end
  - First `str` is one of: TODO does tokenizer handle regex boundaries, or is that only for definitions. Can a regex replacement-type pattern live in literal text space (eg to allow newline or tab escape sequences?)
    - `'LITERAL'`: Basic plain text to appear unchanged
    - `'PRE_DEF'`: Definition from a key/pattern to a replacement value, applied before tokenizing/parsing
    - `'BOUND_DEF'`: Definition from a key/pattern to a replacement value, applied to invocation-bounded tokens
    - `'POST_DEF'`: Definition from a key/pattern to a replacement value, applied to final text following subtree evaluation
    - `'INVOCATION'`: A bounded token string intended to be replaced by a bounded definition
    - `'GROUP'`: A collection of one or more values intended to be selected from by PRNG during evaluation

**Invariants:**
- All syntax characters (eg `<`, `>`, `\`, `:`, `/`) appearing in LITERAL tokens are passed through as-is
- Tokens appear in source order; concatenating all token values reconstructs input
- Token contents contain the syntax/boundaries that defined them

### Definition

**Purpose:** Parsed definition directive from a preo-/bounded-/post-Definition token.

**Fields:**
- `pattern_class` (str): Pattern application timing
  - `'PRE'`: Applied before bounded token parsing
  - `'BOUNDED'`: Applied within invocation boundaries
  - `'POST'`: Applied after all resolution
- `strength` (str): Stack priority
  - `'STRONG'`: Pushes to stack HEAD (checked first)
  - `'WEAK'`: Pushes to stack TAIL (used as fallback)
- `key_is_regex` (bool): Whether key should match as regex
- `value_is_regex` (bool): Whether value should apply as regex replacement
- `key` (str): Pattern to match (literal or regex without delimiters)
- `value` (str): Replacement text (literal or regex with backreferences)

**Invariants:**
- key and value are unescaped (escape characters removed)
- Regex patterns have `/` delimiters already stripped
- pattern_class is always one of: 'PRE', 'BOUNDED', 'POST'
- strength is always one of: 'STRONG', 'WEAK'

### ASTNode Class (Parser Output)

**Purpose:** Represents a semantic unit for evaluation, with content that may contain nested nodes.

**Attributes:**
TODO is this using different classes as different node types, or handled by a field/content difference?
- `node_type` (str): Semantic category
  - `'LITERAL'`: Plain text (literal string from LITERAL tokens) TODO: Store literal as raw strings. No need for the rest of node semantics
  - `'INVOCATION'`: Macro invocation (`< >` boundaries)
    `'MULTI-VALUE`: Block `{}` containing one or more options to select from
- `raw_text` (str): Original text before evaluation
- `is_transparent` (bool): Whether scope changes affect siblings
  `definitions` (`List[Definition]`): All invocation arguments and top-level internal definitions that apply to contents.
- `output_parts` (List[Union[str, ASTNode]]): Mixed literal text and invocation nodes that will turn into output text
  TODO is parts or children a better description

**Invariants:**
TODO still TBD on how to handle/place literals
- All child nodes are either literal strings or ASTNode objects
- Concatenating all literal parts and Node.raw_text produces non-definition content from originals

### MacroContext Class (Evaluator State)

**Purpose:** Object for for managing PRNG and scoped definitions during evaluation.

**Architecture:**
- Deque-based with strong definitions at HEAD (left), weak at TAIL (right)
- Left-to-right iteration ensures strong definitions checked before weak
- Enables lexical scoping with local definitions overriding or defaulting global
- TODO PRNG Object

**Methods:**
- `push(definitions: List[Definition], transparent = False) → None`: Add definitions based on strength with scope-markers based on transparency
  - Strong definitions append to left (HEAD)
  - Weak definitions append to right (TAIL)
REMOVED `pop_strong` and `pop_weak`. There is not need for these as individual functions, at least so far.
- `get_definitions(pattern_class: str) → List[Definition]`: Return definitions matching pattern_class in priority order (left-to-right)

**Invariants:**
- Left-to-right traversal of deque always checks strong definitions before weak
- get_definitions() returns definitions in priority order (strong first, then weak)

---

## Stage 1→2 Interface: Lexer Output (Token Objects)

**Defined in:** LEXER_SPECIFICATION.md

The Lexer produces a sequence of Token objects representing raw-string primitives.

---

## Stage 2→3 Interface: Parser Output (AST Nodes)

**Defined in:** PARSER_SPECIFICATION.md

The Parser produces an Abstract Syntax Tree (AST) where each node represents a semantic element.

---

## Stage 3 Runtime: Evaluator State (MacroContext)

**Defined in:** EVALUATOR_SPECIFICATION.md

The Evaluator recursively turns an AST Node into the concatentation of its evaluated output_parts.

## Subsystem Promises

### Lexer Promises (String → Token)

**Input:**
- Raw string (may contain escape sequences, newlines, syntax characters)
  - Guaranteed to be pre split on parsing-level dividers (typically `|`)
- Ordered List of type, boundary marker Tuples (TODO robustness/safety requirements)
  -(TODO How should line-start to end of line be handled? An end marker of `None` or `'\n'`? And then that implies start-of-line only for the start marker?")

**Output:** Ordered sequence of Token objects

**Guarantees:**
1. Character-by-character processing with no lookahead ambiguity
2. Escape characters and following character are preserved as-is
3. Tokens correspond 1:1 with semantic objects (Literal, Definition, Invocation, etc)
4. Tokens are in source order and reconstruct input when concatenated
5. No information loss (all input characters appear in output)

**See:** LEXER_SPECIFICATION.md for detailed specifications

### Parser Promises (Token → String/Definition/ASTNode)

**Input:** Token object

**Output:** Either a literal text String, a populated Definition, or an ASTNode of appropriate type/content

**Guarantees:**
1. Bounded invocation pairs (default `< >`) create invocation nodes
2. Bounded multi-value group strings create group nodes
5. All definitions are parsed (key/value unescaped, regex detected), with syntax characters stripped

**See:** PARSER_SPECIFICATION.md for detailed specifications

### Evaluator Promises (AST → String)

**Input:** ASTNode root node; MacroContext

**Output:** Final string output with all macros resolved

**Guarantees:**
1. Deterministic: Same input and seed produce identical output
2. Order-dependent: Definitions evaluated left-to-right
3. Scope-isolated: Non-transparent nodes pop their definitions after evaluation
4. Regex-safe: Regex substitutions use proper escaping
5. Single-pass: Tree evaluated exactly once (no multi-pass re-evaluation)

**See:** EVALUATOR_SPECIFICATION.md for detailed specifications

---

## Design Principles

### Separation of Concerns

- **Lexer** handles character-level syntax (escaping, boundaries, line detection) and division into semantic structured units
- **Parser** handles semantic grouping (definition key and value, invocation token and argument, nesting)
- **Evaluator** handles context and scope management and nesting recursion

### Information Preservation

- Each stage preserves input information needed by downstream stages
- Lexer preserves escape information; Parser strips escapes from parsed content appropriately, left in raw_string
- Lexer and Parser simply interpret inputs into containers of semantic meaning, Evaluator applies those meanings with final context
- Lexer and Parser resolve lazily, return only one layer at a time.

### Determinism

- Lexer output is deterministic (no randomness, no context-dependent behavior)
- Parser output is deterministic (no ambiguous syntax, all cases handled)
- Evaluator output is deterministic (PRNG seeded by call, mutated by path, not external state)

---

## Related Documentation

- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing details
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Token → AST parsing roadmap
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - (Future) Detailed parser specs
- [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String evaluation details
- [UNIFIED_PROCESS_PLAN.md](UNIFIED_PROCESS_PLAN.md) - Architecture strategy and rationale
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
