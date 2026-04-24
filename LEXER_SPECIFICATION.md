# Lexer Specification

This document defines the lexical analysis subsystem: the character-by-character processing pipeline that converts raw input strings into a flat, zero-depth `Token` list.

## 1\. System Overview

The Lexer performs the first stage of the Macro Engine pipeline:

```text
Raw Input String → [LEXER] → Token List
```

The Lexer operates strictly under the **Breadth-Eager, Depth-Lazy** paradigm. It is entirely blind to execution logic, random seed generation, or contextual state. Its sole responsibility is to identify top-level structural boundaries and safely encapsulate nested syntax as inert text.

To bypass the catastrophic performance penalties of Python string buffering, the Lexer utilizes an **Interval-Tracking Speculative Architecture**, ensuring O(N) linear time complexity.

---

## 2\. Core Lexing Architecture

### 2.1 Interval-Tracking & Pushdown Automata

Instead of slicing and buffering strings character-by-character, the Lexer runs a single pass over the text.

- It uses independent pushdown automata (stacks) for each configured boundary type (e.g., `<` and `>`).
- When an opening marker is found, its integer index is pushed.
- When a closing marker is found, the stack pops and the `(start_index, end_index)` pair is registered as a "Candidate Interval".
- Discrete markers (like `|` or `$$`) are registered instantly at their integer index without needing a closing pair.

### 2.2 Zero-Depth Interval Culling

To inherently protect nested syntax and isolate user typos (unbalanced brackets), the Lexer applies a culling algorithm at the end of the pass.

- **The Rule:** If a registered token boundary (e.g., `{ }` or `|`) falls strictly within the index bounds of a higher-order boundary (e.g., `< >`), the inner marker is neutralized.
- **The Result:** The Lexer only emits zero-depth tokens. The internal contents of macros and groups remain untouched, flat strings.

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

- **The Mode-Switch Rule:** The opening wrapper (`<<`) must immediately follow the definition's strength marker on the *same line*. If found, EOL termination is suspended.
- **The Nested Block Trap:** The Lexer cannot just blindly scan for the first `>>`. Because blocks can contain other blocks, the Lexer treats `<<` and `>>` as a paired pushdown-automaton boundary like other boundary markers. It only closes the block when the outermost `>>` is reached.
- **Strict Newline Capture:** The Lexer does *not* chomp newlines, it simply captures them in the Definition Token as needed. Leading, trailing, and internal newlines inside the `<< >>` block are preserved perfectly, granting the user explicit control over text flow.

---

## 6\. Lexer-Parser Contract

**What the Lexer guarantees to the Parser:**

1. **No Lookahead Ambiguity:** Processing relies strictly on stateful index tracking, never complex regex lookaheads.
2. **Lossless Reconstruction:** Tokens correspond 1:1 with the input. Concatenating the raw text fields of the output tokens will result in an exact, byte-for-byte duplicate of the input string.
3. **Lazy Isolation:** All—and only—top-level (zero-depth) syntax markers are identified as discrete or bounded tokens. Everything else is guaranteed to be a `TEXT` token.
4. **Data Offloading:** The Lexer outputs strongly typed, clean `Token` objects. It does not attempt to parse definitions into key/value pairs, instantiate AST Nodes, differentiate Invocation variants, or interpret modifiers.
