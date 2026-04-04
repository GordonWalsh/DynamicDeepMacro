# Core Data Types and Subsystem Interfaces

This document defines the shared data structures and contracts between the three processing subsystems: Lexer, Parser, and Evaluator.

## Overview

The macro engine processes text through three sequential stages:

```
String Input
    ↓ [LEXER]
Token List
    ↓ [PARSER]
Abstract Syntax Tree (AST)
    ↓ [EVALUATOR]
Final String Output
```

This document specifies the data structures passed between stages and the invariants guaranteed by each subsystem.

## Stage 1→2 Interface: Lexer Output (Token Objects)

**Defined in:** LEXER_SPECIFICATION.md

The Lexer produces a sequence of Token objects representing raw-string primitives.

### Token Class (Lexer Output)

**Purpose:** Represents an atomic unit identified by the character-by-character lexing process.

**Fields:**
- `token_type` (str): Category of token
  - `'LITERAL'`: Raw text between boundaries
  - `'ESCAPED_CHAR'`: Single character escaped with `\`
  - `'BOUNDED_OPEN'`: Start of `< >` boundary
  - `'BOUNDED_CLOSE'`: End of `< >` boundary
  - `'DEFINITION_LINE'`: Text starting with `:` (definition syntax)
- `value` (str): Unprocessed token content
- `position` (int): Character offset in input string
- `length` (int): Number of characters consumed

**Invariants:**
- All syntax characters (`<`, `>`, `\`, `:`, `/`) appearing in LITERAL tokens are unescaped
- ESCAPED_CHAR tokens contain exactly one character (the escaped character itself)
- DEFINITION_LINE tokens are complete lines (including newline if present in input)
- Tokens appear in source order; concatenating all token values reconstructs input

---

## Stage 2→3 Interface: Parser Output (AST Nodes)

**Defined in:** PARSER_SPECIFICATION.md

The Parser produces an Abstract Syntax Tree (AST) where each node represents a semantic element.

### ASTNode Class (Parser Output)

**Purpose:** Represents a semantic unit for evaluation, with content that may contain nested nodes.

**Attributes:**
- `node_type` (str): Semantic category
  - `'LITERAL'`: Plain text (literal string from LITERAL tokens)
  - `'DEFINITION'`: Definition directive (parsed from DEFINITION_LINE tokens)
  - `'INVOCATION'`: Macro invocation (`< >` boundaries)
  - `'ROOT'`: Top-level container (transparent, no scope)
- `raw_text` (str): Original text before evaluation
- `is_transparent` (bool): Whether scope changes affect siblings (for ROOT nodes)
- `content_parts` (List[Union[str, ASTNode]]): Mixed literal text and nested nodes
- `metadata` (dict): Node-specific data (e.g., definition details, invocation parameters)

**Invariants:**
- ROOT node is transparent (is_transparent=True)
- All child nodes are either literal strings or ASTNode objects
- Concatenating all literal parts (excluding nodes) preserves whitespace and newlines
- Each Definition node is self-contained (key, value, pattern_class, strength)

### Definition (Metadata for DEFINITION Nodes)

**Purpose:** Parsed definition directive from a DEFINITION_LINE token.

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

---

## Stage 3 Runtime: Evaluator State (MacroContext)

**Defined in:** EVALUATOR_SPECIFICATION.md

The Evaluator maintains a context stack during AST traversal.

### MacroContext Class (Evaluator State)

**Purpose:** Double-ended stack for managing definition scope during evaluation.

**Architecture:**
- Deque-based with strong definitions at HEAD (left), weak at TAIL (right)
- Left-to-right iteration ensures strong definitions checked before weak
- Enables lexical scoping with local definitions overriding global

**Methods:**
- `push(definition: Definition) → None`: Add definition based on strength
  - Strong definitions append to left (HEAD)
  - Weak definitions append to right (TAIL)
- `pop_strong() → Definition`: Remove most recent strong definition
- `pop_weak() → Definition`: Remove oldest weak definition
- `get_definitions(pattern_class: str) → List[Definition]`: Return definitions matching pattern_class in priority order (left-to-right)

**Invariants:**
- Left-to-right traversal of deque always checks strong definitions before weak
- pop_strong() removes the leftmost definition pushed as STRONG
- pop_weak() removes the rightmost definition pushed as WEAK
- get_definitions() returns definitions in priority order (strong first, then weak)

---

## Subsystem Promises

### Lexer Promises (String → Token)

**Input:** Raw string (may contain escape sequences, newlines, syntax characters)

**Output:** Ordered sequence of Token objects

**Guarantees:**
1. Character-by-character processing with no lookahead ambiguity
2. All escaped syntax characters are unescaped in LITERAL tokens
3. ESCAPED_CHAR tokens contain single characters only
4. Tokens are in source order and reconstruct input when concatenated
5. No information loss (all input characters appear in output)

**See:** LEXER_SPECIFICATION.md for detailed specifications

### Parser Promises (Token → AST)

**Input:** Sequence of Token objects

**Output:** Rooted ASTNode tree (ROOT node at top, children as nested nodes)

**Guarantees:**
1. ROOT node is transparent (is_transparent=True)
2. DEFINITION tokens are parsed into DEFINITION nodes with Definition metadata
3. LITERAL tokens combined into LITERAL nodes
4. BOUNDED_OPEN/CLOSE pairs create INVOCATION nodes
5. All definitions are parsed (key/value unescaped, regex detected)

**See:** PARSER_SPECIFICATION.md for detailed specifications

### Evaluator Promises (AST → String)

**Input:** ASTNode tree with MacroContext

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

- **Lexer** handles character-level syntax (escaping, boundaries, line detection)
- **Parser** handles semantic grouping (definitions, invocations, nesting)
- **Evaluator** handles context management and output generation

### Information Preservation

- Each stage preserves input information needed by downstream stages
- Lexer preserves escape information; Parser strips escapes after detection
- Parser preserves nesting structure; Evaluator preserves scope order

### Determinism

- Lexer output is deterministic (no randomness, no context-dependent behavior)
- Parser output is deterministic (no ambiguous syntax, all cases handled)
- Evaluator output is deterministic (PRNG seeded by path, not external state)

---

## Related Documentation

- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing details
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Token → AST parsing roadmap
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - (Future) Detailed parser specs
- [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String evaluation details
- [UNIFIED_PARSING_PLAN.md](UNIFIED_PARSING_PLAN.md) - Architecture strategy and rationale
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
