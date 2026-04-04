# Unified Parsing Architecture Plan

> **Note on Current vs Target Architecture:** This document describes the *target* unified parsing architecture. The current implementation in `macro_engine.py` uses a dual-pipeline approach as described in the "Current Architecture" section below.
> 
> For **specification details** on the three-stage pipeline (Lexer, Parser, Evaluator) and their data contracts, refer to:
> - [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) - Shared data types and subsystem contracts
> - [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing specifications
> - [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Token → AST parser implementation
> - [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String evaluation specifications

## Executive Summary

The macro engine currently uses a **dual pipeline** architecture where definition parsing and prompt parsing are separate phases. This plan outlines the transition to a **single unified pipeline** that treats both definitions and literal text as first-class components of a mixed AST, enabling true local scoping, definition composition, and seamless integration.

## Current Architecture (Dual Pipeline)

### Phase 1: Context Parsing
- `PromptEngine._parse_global_context()` processes context_string line-by-line
- Extracts definitions matching pattern: `:[PREFIX][KEY][SEPARATOR][VALUE]`
- Pushes Definition objects to MacroContext stack
- Treated as separate "global" scope

### Phase 2: Prompt Evaluation
- `ASTNode.evaluate()` receives prompt text
- `_lex_string()` performs character-by-character scan
- Identifies bounded tokens (`< >`) only
- Pre-patterns applied before lexing, post-patterns applied after resolution
- Treated as separate "local" scope

### Limitations
1. **No true scoping**: Definitions pushed during evaluation cannot be isolated to subtrees
2. **Artificial separation**: "Global" vs "Local" is a false dichotomy; both are the same context stack
3. **Definition composition**: Definitions in context string cannot reference other definitions
4. **Asymmetric parsing**: Context and prompt use different parsing rules and patterns
5. **Text loss**: Literal text in context string is ignored; only definitions are processed

## Target Architecture (Unified Pipeline)

### Single Integrated Lexer
A unified character-by-character pushdown automaton that produces a **mixed AST** containing:

```
MixedAST:
  ├─ DefinitionNode(pattern_class, strength, key_is_regex, value_is_regex, key, value)
  ├─ LiteralNode(text, preserve_newlines=True)
  ├─ InvocationNode(raw_text, is_regex, content_parts=[...])
  ├─ DefinitionNode(...)
  ├─ LiteralNode(...)
  └─ InvocationNode(...)
```

### Parsing Rules
The unified lexer handles (in order of specificity):

1. **Escape sequences**: `\` followed by syntax character (`\:`, `\<`, `\>`, `\/`, `\\`)
2. **Definition lines**: Text starting with `:` followed by definition syntax
3. **Bounded tokens**: `< >` pairs containing key or parameterized invocations
4. **Literal text**: Everything else, preserving newlines and original spacing

### Evaluation Strategy

1. **Top-level evaluation**: Root ASTNode with transparent=True
2. **Process mixed AST sequentially**:
   - DefinitionNode: Push definition to context stack
   - LiteralNode: Append to output, preserving newlines
   - InvocationNode: Apply pre-patterns, resolve via context, apply post-patterns, recurse
3. **Scope management**:
   - Transparent nodes (parent=True) do not create scope boundaries
   - Opaque nodes pop their definitions after evaluation
   - Siblings are isolated unless parent is transparent

## Implementation Roadmap

### Phase 1: Prepare Infrastructure
- [ ] Rename `_parse_global_context()` to `_parse_context()` to indicate both global and local parsing
- [ ] Create DefinitionNode, LiteralNode, and InvocationNode classes
- [ ] Update ASTNode to handle mixed node types
- [ ] Add node_type field to distinguish evaluation behavior

### Phase 2: Extend Lexer
- [ ] Modify `_lex_string()` to detect definition syntax (`:` at line start)
- [ ] Add definition routing logic to extract and create DefinitionNode objects
- [ ] Preserve literal text between definitions
- [ ] Maintain all escape sequence handling for syntax characters

### Phase 3: Update Evaluation
- [ ] Extend `evaluate()` to process DefinitionNode objects
- [ ] Push definitions to context stack when encountered
- [ ] Apply scope pop logic for non-transparent nodes
- [ ] Preserve order-dependent evaluation (left-to-right for definitions)

### Phase 4: Merge Parsers
- [ ] Remove separate `_parse_global_context()` method
- [ ] Update `PromptEngine.__init__()` to use unified parser
- [ ] Accept single input string with mixed definitions and prompt text
- [ ] Maintain backward compatibility with existing test suite

### Phase 5: Enhanced Features
- [ ] Support parameterized invocations: `<key|:arg:val>`
- [ ] Implement local argument scoping
- [ ] Add transparent node support for scope sharing
- [ ] Support nested invocation syntax

## Key Design Decisions

### 1. Newline Preservation
Literal nodes preserve newlines to maintain prompt structure. This allows:
- Multi-line definitions in context
- Multi-line prompts with maintained formatting
- Definition blocks separated by blank lines

### 2. Order-Dependent Evaluation
Definitions are evaluated in order encountered:
- Earlier definitions pushed to stack first
- Strong definitions override earlier weak definitions
- Definitions in subtrees don't affect siblings (unless transparent)

### 3. Regex Detection
Patterns `/ ... /` are detected both in contexts AND invocations:
- Key can be regex: `:/pattern/:literal` (pre-pattern)
- Value can be regex: `:literal:/pattern/` (substitution replacement)
- Both can be regex: `:/key_pattern/:/value_pattern/`
- Detection: pattern must start and end with `/` and ending `/` cannot be escaped

### 4. Escape Semantics
Backslash escapes only syntax characters (defined in SYNTAX_CHARACTERS):
- `:` (separator)
- `<` (invocation start)
- `>` (invocation end)
- `/` (pattern delimiter)
- `\` (escape character itself)

This is stricter than Python/regex escaping and prevents accidental character loss.

## Benefits of Unification

1. **True Local Scoping**: Definitions in function bodies don't leak to siblings
2. **Definition Composition**: Definitions can reference other definitions
3. **Consistent Semantics**: Same parsing rules and escape semantics everywhere
4. **Flexible Context**: Both "global" and "local" are the same mechanism
5. **Simpler Architecture**: Single lexer, single evaluator, one set of rules
6. **Better Extensibility**: New node types (LoRA blocks, comments) fit naturally

## Backward Compatibility

The unified architecture maintains compatibility with existing code:
- Existing test suite continues to pass
- Context string format remains identical
- Prompt format remains identical
- Parser is transparent to callers

The only visible change is that both context and prompt are processed by the same unified pipeline.

## Future Extensions

### Multi-Boundary Support
Extend lexer to handle `{ }` for other token types:
- `{a|b|c}` for weighted selection
- `{...|...}` for conditional branching
- Proper nesting: `<a {b|c} d>`

### Parameterized Invocations
Support local argument passing:
- `<key|:arg:val>` for strong local definitions
- `<key|:arg::val>` for weak local definitions
- Scope isolation: arguments only affect key evaluation

### LoRA Wrappers
Native support for `[group: <lora:...>]` syntax:
- Automatically routes to trace log
- Strips wrapper in final output
- Supports composition with other definitions

### Comment Syntax
Allow inline comments without affecting output:
- `# comment` at line start
- Useful for documentation in context strings
