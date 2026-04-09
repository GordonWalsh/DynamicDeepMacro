# Parser Specification

> **Note on Scope:** This document covers the **Parser** stage (Token → AST) of the three-stage processing pipeline. For comprehensive parser specifications including data structure contracts and interface guarantees, see [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md). For implementation roadmap details and design decisions, see [UNIFIED_PROCESS_PLAN.md](UNIFIED_PROCESS_PLAN.md).
>
> **Three-Stage Pipeline:**
> 1. [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token
> 2. PARSER_SPECIFICATION.md (this document) - Token → AST
> 3. [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String

## Overview

This specification outlines the methodical implementation of a Token-to-AST parser that converts the `Token` objects from the Lexer into a meaningful Abstract Syntax Tree (AST) node representing literals, definitions, invocations, and other semantic constructs. The parser will be built incrementally, with each milestone adding features while maintaining test coverage and clean architecture.

## Core Architecture Principles

- **Incremental Development**: Each milestone builds on the previous, with working code and tests at every step.
- **Semantic Clarity**: AST nodes have clear, typed properties that represent their meaning (e.g., `DefinitionNode` with pattern_class, strength, etc.).
TODO Verify if using typed nodes or separate contents
- **Unified Input**: The parser accepts a list of `Token` objects and produces a root AST node with children.
- **Error Handling**: Graceful degradation for malformed input, with clear error messages.
- **Test-Driven**: New tests validate each feature before implementation proceeds.
- **Documentation**: Inline comments and docstrings explain node semantics and parser logic.

## Milestone 1: Define AST Node Classes

**Goal**: Establish the foundational AST node types that represent different semantic constructs.

**Implements Features**:
- `LiteralNode`: Represents plain text spans (e.g., from literal tokens).
- `DefinitionNode`: Represents definition syntax (e.g., `:key:value` patterns).
- `InvocationNode`: Represents bounded token invocations (e.g., `<key>` or `{choice}`).
- Base `ASTNode` class with common properties (e.g., `node_type`, `raw_text`).

**Architecture**:
- Use dataclasses for immutable node structures.
- Each node type has specific fields (e.g., `DefinitionNode` has `pattern_class`, `strength`, `key`, `value`).
  TODO Verify typed nodes
- Nodes can have children for nested structures.
- Nodes should be pure semantic containers; they should not carry runtime state such as a context deque or PRNG object.
- The evaluation-relevant property `is_transparent` belongs to the AST node model because transparency is derived from parsed syntax and affects later scope handling.
- Two viable designs:
  - Subclassing AST node types (`LiteralNode`, `DefinitionNode`, `InvocationNode`) with shared base fields.
  - A single `ASTNode` wrapper with a typed `content` field carrying a union of literal/definition/invocation payloads.
  - For clarity and maintainability, the subclassed approach is preferred.
      TODO explain this decision

**Implementation**:
- Create `ast_nodes.py` module with node definitions.
- Import `Token` from `core_engine.py` for type hints.

**Tests**:
- Unit tests for node creation and equality.
- Tests for invalid node construction (e.g., missing required fields).

**Documentation**:
- Docstrings for each node class explaining their purpose and fields.
- Comments on how nodes map to Token types.

## Milestone 2: Basic Token-to-Node Conversion

**Goal**: Implement a parser that converts individual Tokens to corresponding AST nodes.

**Implements Features**:
- Parser function `parse_token(token: Token) -> ASTNode` that produces a root node with children.
- Handle literal tokens → `LiteralNode`.
- Handle bounded tokens → `InvocationNode` (initially simple, no nested parsing).
- Root node as a container for the sequence of parsed nodes.

**Architecture**:
- Sequential parsing: Process tokens left-to-right, creating nodes.
- Each token becomes a node 1:1.

**Implementation**:
- Create `parser.py` module with `parse_token` function.
- Implement a generic dispatch wrapper that steers tokens to specialized sub-parser functions based on token type.

**Tests**:
- Test parsing a single literal token.
- Test parsing a single bounded token.
- Validate node properties match Token data.

**Documentation**:
- Function docstrings explaining input/output.
- Comments on token-to-node mapping logic.

## Milestone 3: Definition Syntax Parsing

**Goal**: Extend parser to recognize and parse definition tokens into `DefinitionNode` objects.

**Implements Features**:
- Detect definition patterns in tokens (e.g., tokens containing `:key:value`).
- Parse definition components: pattern_class (`:<`, `:>`, `:`), strength (`:` vs `::`), key/value with regex detection.
- Create `DefinitionNode` with parsed properties.

**Architecture**:
- Definition parsing logic within `parse_token` or a dedicated helper.
- Reuse existing regex detection from `macro_engine.py` for consistency.
- The existing `_parse_global_context` behavior should migrate from `macro_engine.py` into the definition parser.

**Implementation**:
- Add definition parsing logic to `parser.py`.
- Handle escaped characters in definitions.

**Tests**:
- Test parsing simple bounded definitions (e.g., `:key:value`).
- Test pre/post patterns (e.g., `:<key:value>`).
- Test regex keys/values (e.g., `:/key/:/value/`).
- Test escaped syntax in definitions.

**Documentation**:
- Detailed comments on definition syntax grammar.
- Examples of token-to-DefinitionNode conversion.

## Milestone 4: Nested Invocation Parsing

REMOVED Incorrect description. Nesting is handled recursively, one layer at a time.

## Milestone 5: Unified Parser Integration

**Goal**: Integrate the parser with the unified lexer and update the engine interface.

**Implements Features**:
- Modify `PromptEngine` to use the new parser instead of old dual-pipeline.
- Accept a single input string, lex it, then parse to AST.
- Update evaluation to traverse the AST.

**Architecture**:
- `PromptEngine` now: lex → parse → evaluate AST.

**Implementation**:
- Update `core_engine.py` to import and use `parser.py`.
- Replace old `_lex_string` and `_parse_global_context` with unified flow.

**Tests**:
- End-to-end tests: Input string → final output matches expected.
- Regression tests ensure old functionality still works.
- Test mixed definitions and invocations in single input.

**Documentation**:
- Updated class docstrings for `PromptEngine`.
- Integration notes on how lexer and parser work together.

## Milestone 6: Error Handling and Edge Cases

**Goal**: Add robustness for malformed input and edge cases.

**Implements Features**:
- Error nodes or exceptions for invalid syntax.
- Handling of unclosed boundaries, malformed definitions.
- Recovery mechanisms to continue parsing.

**Architecture**:
- Parser returns partial AST or error indicators.
- Logging or warnings for issues.

**Implementation**:
- Add error handling logic to `parser.py`.

**Tests**:
- Test malformed definitions.
- Test unclosed invocations.
- Test recovery from errors.

**Documentation**:
- Error handling guidelines.
- Examples of error cases.

## Final Milestone: Optimization and Cleanup

**Goal**: Refine performance, remove cruft, and finalize the parser.

**Implements Features**:
- Performance optimizations (e.g., avoid unnecessary copies).
- Clean up temporary code and stubs.
- Full documentation and examples.

**Architecture**:
- Finalize the AST node hierarchy.
- Ensure clean separation of concerns.

**Implementation**:
- Code reviews and refactoring.

**Tests**:
- Performance benchmarks.
- Comprehensive integration tests.

**Documentation**:
- Complete API documentation.
- User guide for the unified parser.

---

## Related Documentation

- [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) - ASTNode and Definition specifications
- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing
- [EVALUATOR_SPECIFICATION.md](EVALUATOR_SPECIFICATION.md) - AST → String evaluation
- [UNIFIED_PROCESS_PLAN.md](UNIFIED_PROCESS_PLAN.md) - Architecture strategy and rationale
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
