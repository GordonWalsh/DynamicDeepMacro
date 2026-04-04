# Lexer Specification

This document specifies the lexing subsystem: character-by-character processing of raw input strings into Token objects.

## Overview

The Lexer performs the first stage of processing:

```
Raw Input String → [CHARACTER-BY-CHARACTER LEXING] → Token List
```

The Lexer's responsibility is to:
1. Detect escape sequences (`\` followed by syntax characters)
2. Identify boundaries (`< >` for bounded tokens)
3. Identify definition lines (lines starting with `:`)
4. Preserve all other characters as literals
5. Produce an ordered sequence of Token objects

**See:** [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) for Token class specification and lexer output guarantees.

## Escape Sequences

The backslash character (`\`) escapes only syntax characters. This prevents accidental information loss.

### Syntax Characters

Characters that can be escaped:
- `:` (definition/pattern separator)
- `<` (bounded token start)
- `>` (bounded token end)
- `/` (pattern delimiter)
- `\` (escape character itself)

### Escape Semantics

**Rule:** A backslash followed by a syntax character is treated as an escape sequence:
- The backslash is consumed (removed)
- The following syntax character is treated as literal (not special)
- The literal character appears in the next LITERAL or ESCAPED_CHAR token

**Non-Syntax Characters:** Backslashes followed by non-syntax characters are NOT escape sequences:
- Both the backslash and following character are treated as literals
- Examples: `\n`, `\t`, `\_` all appear literally in output (no interpretation)

### Examples

| Input | Output | Explanation |
|-------|--------|---|
| `\<literal\>` | ESCAPED_CHAR(`<`) + LITERAL(`literal`) + ESCAPED_CHAR(`>`) | Backslashes escape the boundary markers |
| `key\:with\:colons` | LITERAL with `:` characters | Backslashes prevent colons from being special |
| `\\/pattern\\/` | LITERAL with `/pattern/` | First slash escaped; second slash is literal |
| `\\` | ESCAPED_CHAR(`\`) | Escape the escape character itself |
| `\n` | LITERAL with `\n` | Backslash-n is NOT escaped; appears literally |

---

## Bounded Token Boundaries

Bounded tokens are delimited by angle brackets: `< >`. These mark invocation boundaries.

### Boundary Detection

**Opening Boundary:** `<` (unescaped)
- Starts a BOUNDED_OPEN token
- Must not be preceded by `\` (escape character)

**Closing Boundary:** `>` (unescaped)
- Starts a BOUNDED_CLOSE token
- Must not be preceded by `\` (escape character)
- Matches innermost unmatched BOUNDED_OPEN

### Nesting Rules

Boundaries can nest: `<outer <inner> after>` is valid

- Each `<` opens a new level
- Each `>` closes the innermost level
- Unclosed `<` at end of string is emitted as LITERAL (graceful degradation)

### Examples

| Input | Tokens | Notes |
|-------|--------|---|
| `<simple>` | BOUNDED_OPEN + LITERAL(`simple`) + BOUNDED_CLOSE | Simple invocation |
| `<a<b>c>` | BOUNDED_OPEN + LITERAL(`a`) + BOUNDED_OPEN + LITERAL(`b`) + BOUNDED_CLOSE + LITERAL(`c`) + BOUNDED_CLOSE | Nested boundaries |
| `<unclosed` | LITERAL(`<unclosed`) | Unclosed boundary at EOF |
| `text<a>text` | LITERAL(`text`) + BOUNDED_OPEN + ... | Boundaries within literal text |

---

## Definition Lines

Lines starting with an unescaped `:` are definition directives.

### Definition Line Detection

**Rule:** A line starts with `:` if:
1. After any preceding whitespace, the first character is `:`
2. The `:` is not escaped (not preceded by `\`)

### Definition Content

Definition syntax is NOT parsed by the Lexer; the entire line is treated as a DEFINITION_LINE token for the Parser to handle.

**Examples:**
- `:<old:new` → DEFINITION_LINE token
- `::[key]::[value]` → DEFINITION_LINE token
- `:>pattern:replacement` → DEFINITION_LINE token
- `\:not a definition` → LITERAL token (escaped colon)

---

## Literal Text

All characters that are not part of escape sequences, boundaries, or definition lines are treated as literal text.

### Literal Preservation

- Whitespace is preserved (spaces, tabs, newlines)
- Formatting is preserved (indentation, line breaks)
- Character encoding is preserved as-is

### Newline Handling

Newlines are preserved in literal text and used to detect definition line boundaries:
- `\n` (LF) is preserved
- `\r\n` (CRLF) is preserved
- Used to determine when a new line starts (for definition detection)

---

## Character-by-Character Lexing Algorithm

The Lexer uses a pushdown automaton to process input character-by-character.

### Stack Frame Structure

Each nesting level of bounded tokens maintains a stack frame:

```python
{
    'parts': [...],      # Mixed list of literal strings and nested boundaries
    'literal': [...]     # Character buffer for current literal span
}
```

### Processing Steps

**For each character in input:**

1. **Check escape sequences**
   - If previous char is `\` and current char is syntax character:
     - Emit ESCAPED_CHAR token with current character
     - Continue (escape consumed)
   - Otherwise, continue to step 2

2. **Check boundaries (if not in escape)**
   - If current char is `<` (unescaped):
     - Emit current literal buffer as LITERAL token (if non-empty)
     - Create new stack frame for nested level
     - Emit BOUNDED_OPEN token
     - Continue
   - If current char is `>` (unescaped):
     - Emit current literal buffer as LITERAL token (if non-empty)
     - Pop stack frame
     - Emit BOUNDED_CLOSE token
     - Continue
   - Otherwise, continue to step 3

3. **Check definition line (if at line start)**
   - If current char is `:` AND position is at line start:
     - Emit current literal buffer as LITERAL token (if non-empty)
     - Scan forward to end of line
     - Emit DEFINITION_LINE token with full line
     - Continue
   - Otherwise, continue to step 4

4. **Accumulate literal text**
   - Add current character to literal buffer
   - Continue

**At end of input:**
- Emit any remaining literal buffer as LITERAL token
- If any bounded tokens are unclosed, emit them as LITERAL

### Implementation Notes

- Character-by-character processing prevents lookahead ambiguity
- Escape state is tracked (was previous character a backslash?)
- Stack depth tracked for nesting validation
- No regex matching in lexer (character-only operations)

---

## Current Implementation Status

### Implemented in `macro_engine.py`

- `ASTNode._lex_string()`: Character-by-character pushdown automaton
  - Handles `< >` boundary detection
  - Handles escape sequences (`\<`, `\>`, `\\`)
  - Detects nested boundaries
  - Gracefully handles unclosed boundaries
  - Preserves literal text with newlines

- `PromptEngine._unescape()`: Syntax-character-only unescaping
  - Strips `\` before `:`, `<`, `>`, `/`, `\`
  - Preserves backslashes before non-syntax characters

### Not Yet Implemented

- `Token` class (wrapper for token_type, value, position, length)
- Separate DEFINITION_LINE token type (currently definitions are parsed in context string phase)
- Unified lexing of both context and prompt (currently split into two phases)
- Multi-boundary support (only `< >` currently; `{ }` and `[ ]` not supported)

---

## Examples

### Example 1: Simple Text with Invocation

**Input:**
```
Generate <adjective> <animal>
```

**Lexer Output:**
```
LITERAL("Generate ")
BOUNDED_OPEN
LITERAL("adjective")
BOUNDED_CLOSE
LITERAL(" ")
BOUNDED_OPEN
LITERAL("animal")
BOUNDED_CLOSE
```

### Example 2: Escaped Characters

**Input:**
```
Literal \<angle\> and \:colon\:
```

**Lexer Output:**
```
LITERAL("Literal ")
ESCAPED_CHAR("<")
LITERAL("angle")
ESCAPED_CHAR(">")
LITERAL(" and ")
ESCAPED_CHAR(":")
LITERAL("colon")
ESCAPED_CHAR(":")
```

### Example 3: Nested Boundaries

**Input:**
```
<outer <inner> text>
```

**Lexer Output:**
```
BOUNDED_OPEN
LITERAL("outer ")
BOUNDED_OPEN
LITERAL("inner")
BOUNDED_CLOSE
LITERAL(" text")
BOUNDED_CLOSE
```

### Example 4: Definition Line

**Input:**
```
:color:blue
Generate a <color> sky
```

**Lexer Output:**
```
DEFINITION_LINE(":color:blue")
LITERAL("Generate a ")
BOUNDED_OPEN
LITERAL("color")
BOUNDED_CLOSE
LITERAL(" sky")
```

---

## Lexer-Parser Contract

**What the Lexer guarantees to the Parser:**

1. All tokens appear in source order
2. Concatenating all LITERAL and ESCAPED_CHAR token values (in order) reconstructs the original input
3. ESCAPED_CHAR tokens contain unescaped syntax characters
4. DEFINITION_LINE tokens are complete lines (including trailing newline if present)
5. BOUNDED_OPEN and BOUNDED_CLOSE tokens are properly nested
6. No syntax characters appear unescaped in LITERAL tokens (except within boundaries)

**What the Lexer requires from input:**

1. Valid UTF-8 text (or compatible encoding)
2. No restrictions on content (any characters allowed in literals)

---

## Related Documentation

- [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) - Token class and lexer output contract
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Parser specifications (Token → AST)
- [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - Evaluator specifications (AST → String)
- [UNIFIED_PARSING_PLAN.md](UNIFIED_PARSING_PLAN.md) - Architecture strategy and rationale
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
