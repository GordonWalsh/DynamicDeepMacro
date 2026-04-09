# Lexer Specification

This document defines the lexical analysis subsystem: the character-by-character processing pipeline that converts raw input strings into a flat, zero-depth `Token` list.

## 1\. System Overview

The Lexer performs the first stage of the Macro Engine pipeline:

```text
Raw Input String → [LEXER] → Token List
```

The Lexer operates strictly under the **Breadth-Eager, Depth-Lazy** paradigm. It is entirely blind to execution logic, random seed generation, or contextual state. Its sole responsibility is to identify top-level structural boundaries and safely encapsulate nested syntax as inert text.

To bypass the catastrophic performance penalties of Python string buffering, the Lexer utilizes an **Interval-Tracking Speculative Architecture**, ensuring O(N) linear time complexity.

* * *

## 2\. Core Lexing Architecture

### 2.1 Interval-Tracking & Pushdown Automata

Instead of slicing and buffering strings character-by-character, the Lexer runs a single pass over the text.

* It uses independent pushdown automata (stacks) for each configured boundary type (e.g., `<` and `>`).
* When an opening marker is found, its integer index is pushed.
* When a closing marker is found, the stack pops, and the `(start_index, end_index)` pair is registered as a "Candidate Interval".
* Discrete markers (like `|` or `$$`) are registered instantly at their integer index without needing a closing pair.

### 2.2 Zero-Depth Interval Culling

To inherently protect nested syntax and isolate user typos (unbalanced brackets), the Lexer applies a culling algorithm at the end of the pass.

* **The Rule:** If a registered token boundary (e.g., `{ }` or `|`) falls strictly within the index bounds of a higher-order boundary (e.g., `< >`), the inner marker is neutralized.
* **The Result:** The Lexer only emits zero-depth tokens. The internal contents of macros and groups remain untouched, flat literal strings.

* * *

## 3\. Token Configuration & State

### 3.1 Dynamic Syntax Injection

The Lexer does not hardcode its boundary markers. It receives a `SyntaxConfig` object at runtime mapping characters to a `TokenType` Enum. This prevents memory bloat on individual `Token` objects, which no longer store their bounding strings.

**Supported Token Types:**

* `LITERAL`: Plain text.
* `DEFINITION`: Bounded macro, pre-pattern, or post-pattern rules.
* `INVOCATION`: Context Stack lookup wrappers (`< >`).
* `GROUP`: Multi-value PRNG reduction wrappers (`{ }`).
* `SPLIT`: Zero-depth option dividers (`|`).
* `MODIFIER`: Math/Quantity rules (`2$$`).

* * *

## 4\. Escape Sequences & Formatting

### 4.1 Selective Escape Stripping

To avoid the "Slash Collision Trap" (destroying file paths or standard regex inputs), the Lexer employs selective escaping using the backslash (`\`).

* A backslash only acts as an escape character if it immediately precedes a custom structural syntax marker defined in the `SyntaxConfig` (e.g., `\<`, `\:`).
* If escaped, the Lexer ignores the marker for boundary tracking.
* **Standard escapes (e.g., `\n`, `\t`, `\C:\`) are treated as pure literal text** and are not processed or stripped by the Lexer.

* * *

## 5\. Definition Boundary Rules

The Lexer handles macro definitions (`:key:value`) using a dual-mode termination strategy to safely isolate values.

### 5.1 End-of-Line (EOL) Termination (Default)

By default, when the Lexer encounters a zero-depth definition header, it tracks the value string until it hits an unescaped newline character (`\n`) or the end of the file.

### 5.2 The Multi-Line Value Wrapper (`<< ... >>`)

To support "Container Macros" and multi-line values, the Lexer supports explicit block boundaries that override the EOL termination rule.

* **The Mode-Switch Rule:** The opening wrapper (`<<`) must immediately follow the definition's strength marker on the _same line_ (optional spaces/tabs allowed, but no newlines). If found, EOL termination is suspended.
* **The Nested Block Trap:** The Lexer cannot just blindly scan for the first `>>`. Because blocks can contain other blocks, the Lexer treats `<<` and `>>` as a paired pushdown-automaton boundary. It increments a counter for nested `<<` markers and only closes the block when the outermost `>>` is reached.
* **Strict Literal Capture:** The Lexer does _not_ chomp newlines. Leading, trailing, and internal newlines inside the `<< >>` block are preserved perfectly, granting the user explicit control over text flow.

* * *

## 6\. Lexer-Parser Contract

**What the Lexer guarantees to the Parser:**

1. **No Lookahead Ambiguity:** Processing relies strictly on stateful index tracking, never complex regex lookaheads.
2. **Lossless Reconstruction:** Tokens correspond 1:1 with the input. Concatenating the raw text fields of the output tokens will result in an exact, byte-for-byte duplicate of the input string.
3. **Lazy Isolation:** All—and only—top-level (zero-depth) syntax markers are identified as discrete or bounded tokens. Everything else is guaranteed to be a `LITERAL` token.
4. **Data Offloading:** The Lexer outputs strongly typed, clean `Token` objects. It does not attempt to parse definitions into key/value pairs, instantiate AST Nodes, or interpret modifiers.
