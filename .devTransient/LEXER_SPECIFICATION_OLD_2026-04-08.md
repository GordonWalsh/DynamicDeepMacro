# Lexer Specification

This document specifies the lexing subsystem: character-by-character processing of raw input strings into Token objects.

## Overview

The Lexer performs the first stage of processing:

```
Raw Input String → [CHARACTER-BY-CHARACTER LEXING] → Token List
```

The Lexer's responsibility is to:
1. Detect valid, matched, top-level boundary marker pairs, ignoring nested, escaped, or those captured by higher-priority marker pairs
2. Produce an ordered sequence of Token objects containing either literal text, or complete top-level bounded token strings with boundaries intact

**See:** [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) for Token class specification and lexer output guarantees.

## Escape Sequences

For the purposes of the lexer, the escape character, default backslash (`\`), just invalidates a boundary from being counted, removing and/or resolving the escape character is deferred, at this point it is just treated as part of the surrounding literal text.

---

## Bounded Token Boundaries

Bounded tokens are delimited by boundary markers, by default curly braces `{ }` and angle brackets: `< >`. These mark points where a Token object should be split off from the stream of text.

REMOVED Invalid description of individual tokens for boundary markers and content

### Nesting Rules

Boundaries can nest: `<outer <inner> after>` is valid. The lexer only emits Tokens of the top-level boundaries, lower-level nested pairs will be handled by a parser's or evaluator's later function call.

- Each `<` opens a new level
- Each `>` closes the innermost level
- Unclosed `<` at end of string is emitted as LITERAL (graceful degradation)

REMOVED The examples here were not following this projects lexing architecture
---
## Priority Semantics
TODO Build from implementation and `syntax.json`
---
## Literal Text

All characters that are not part of valid matching bounded tokens are treated as literal text.

### Literal Preservation

- Whitespace is preserved (spaces, tabs, newlines)
- Formatting is preserved (indentation, line breaks)
- Character encoding is preserved as-is

### Newline Handling

Newlines are preserved in literal text, but will split following text into a separate Token. This preserves start-of-line delineations for the parser (does not have to split a Token into a literal text Node and a following Definition line Node):
- `\n` (LF) is preserved
- `\r\n` (CRLF) is preserved

---

## Character-by-Character Lexing Algorithm

The Lexer uses a pushdown automaton to process input character-by-character.

### Stack Frame Structure
TODO verify if this description is correct, many other details were wrong
Each nesting level of bounded tokens maintains a stack frame:

```python
{
    'parts': [...],      # Mixed list of literal strings and nested boundaries
    'literal': [...]     # Character buffer for current literal span
}
```

### Processing Steps

NOTE contents removed since they were not for this project's lexing strategy


---

## Lexer-Parser Contract

**What the Lexer guarantees to the Parser:**

1. All tokens appear in source order
2. The text contents of tokens concatenate into an exact duplicate of the input string
2. All top-level boundary marker pairs are detected according to input order priority
4. Literal text does not contain any internally matched boundary markers
5. Bounded tokens contain their boundary markers in both the text content and the boundary field
6. Bounded token text contents are a flat string, no handling of nesting or interpreting contents.

**What the Lexer requires from input:**

1. Valid UTF-8 text (or compatible encoding)
2. No restrictions on content (any characters allowed in literals)

---

## Related Documentation

- [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) - Token class and lexer output contract
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Parser specifications (Token → AST)
- [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - Evaluator specifications (AST → String)
- [UNIFIED_PROCESS_PLAN.md](UNIFIED_PROCESS_PLAN.md) - Architecture strategy and rationale
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
