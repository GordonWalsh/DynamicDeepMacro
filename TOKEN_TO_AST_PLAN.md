# Token to AST Node Parser Implementation Plan

## Overview
This plan outlines the methodical implementation of a Token-to-AST parser that converts the stream of `Token` objects from `lexer.py` into a meaningful Abstract Syntax Tree (AST) with nodes representing literals, definitions, invocations, and other semantic constructs. The parser will be built incrementally, with each milestone adding features while maintaining test coverage and clean architecture.

## Core Architecture Principles
- **Incremental Development**: Each milestone builds on the previous, with working code and tests at every step.
- **Semantic Clarity**: AST nodes have clear, typed properties that represent their meaning (e.g., `DefinitionNode` with pattern_class, strength, etc.).
- **Unified Input**: The parser accepts a list of `Token` objects and produces a root AST node with children.
- **Error Handling**: Graceful degradation for malformed input, with clear error messages.
- **Test-Driven**: New tests validate each feature before implementation proceeds.
- **Documentation**: Inline comments and docstrings explain node semantics and parser logic.

## Milestone 1: Define AST Node Classes
**Goal**: Establish the foundational AST node types that represent different semantic constructs.

**Features Implemented**:
- `LiteralNode`: Represents plain text spans (e.g., from literal tokens).
- `DefinitionNode`: Represents definition syntax (e.g., `:key:value` patterns).
- `InvocationNode`: Represents bounded token invocations (e.g., `<key>` or `{choice}`).
- Base `ASTNode` class with common properties (e.g., `node_type`, `raw_text`).
    - Would this by like an `ASTNode` has a `NodeContent` field that can be filled by a `TextLiteral` or `Definition` or `Invocation`?

**Architecture**:
- Use dataclasses for immutable node structures.
- Each node type has specific fields (e.g., `DefinitionNode` has `pattern_class`, `strength`, `key`, `value`).
- Nodes can have children for nested structures.
- Nodes should be pure semantic containers; they should not carry runtime state such as a context deque or PRNG object.
- The evaluation-relevant property `is_transparent` belongs to the AST node model because transparency is derived from parsed syntax and affects later scope handling.
- Two viable designs:
  - Subclassing AST node types (`LiteralNode`, `DefinitionNode`, `InvocationNode`) with shared base fields.
  - A single `ASTNode` wrapper with a typed `content` field carrying a union of literal/definition/invocation payloads.
  - For clarity and maintainability, the subclassed approach is preferred.
- I think the nodes themselves don't have fields for a context deque or a PRNG object since those are elements of the evaluation lifecycle and the node objects themselves are just containers for meanings.
    - I think that the outer `ASTNode` frame does need to have a field for `isTransparent` though, since that's derived from the parsed syntax and important to the evaluation lifecycle.

**Implementation**:
- Create `ast_nodes.py` module with node definitions.
- Import `Token` from `lexer.py` for type hints.
    - TODO I'm not sure of the typical structure for python projects like this, would we want to have all of our "data object" classes defined in a single central file?

**Tests**:
- Unit tests for node creation and equality.
- Tests for invalid node construction (e.g., missing required fields).

**Documentation**:
- Docstrings for each node class explaining their purpose and fields.
- Comments on how nodes map to Token types.

## Milestone 2: Basic Token-to-Node Conversion
**Goal**: Implement a parser that converts individual Tokens to corresponding AST nodes.

**Features Implemented**:
- Parser function `parse_tokens(tokens: List[Token]) -> ASTNode` that produces a root node with children.
- Handle literal tokens → `LiteralNode`.
- Handle bounded tokens → `InvocationNode` (initially simple, no nested parsing).
- Root node as a container for the sequence of parsed nodes.

**Architecture**:
- Sequential parsing: Process tokens left-to-right, creating nodes.
- No nesting yet; each token becomes a direct child of the root.

**Implementation**:
- Create `parser.py` module with `parse_tokens` function.
- Implement a generic dispatch wrapper that steers tokens to specialized sub-parser functions based on token type.

**Tests**:
- Test parsing a single literal token.
- Test parsing a single bounded token.
- Test parsing mixed sequences (e.g., literal + bounded + literal).
- Validate node properties match Token data.

**Documentation**:
- Function docstrings explaining input/output.
- Comments on token-to-node mapping logic.

## Milestone 3: Definition Syntax Parsing
**Goal**: Extend parser to recognize and parse definition tokens into `DefinitionNode` objects.

**Features Implemented**:
- Detect definition patterns in tokens (e.g., tokens containing `:key:value`).
- Parse definition components: pattern_class (`:<`, `:>`, `:`), strength (`:` vs `::`), key/value with regex detection.
- Create `DefinitionNode` with parsed properties.

**Architecture**:
- Definition parsing logic within `parse_tokens` or a dedicated helper.
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
**Goal**: Support nested structures within invocation tokens.

**Features Implemented**:
- Parse nested tokens inside bounded tokens (e.g., `<outer <inner>>`).
- Create tree structures where `InvocationNode` can have child nodes.
- Handle multiple boundary types (`< >`, `{ }`).
    - If the content string is not "flat", ie it contains any sort of boundary markers, then it should be sent to the lexer first.
        - TODO not sure if it's better to run some fast checks in regex for the possible existance of a bounded token (ie match to `<startMarker>.*<endMarker>`) before sending it away, or just directly send it to the lexer to send it to get parsed as an `ASTNode` to get evaluated back as a (trusted) flat string literal.
            - For the sake of avoiding closed loop cycling, if a post-pattern caused that `ASTNode` evaluation to come back with a valid bounded token inside, should it still be treated as a flat literal or should it get lexed-parsed-evaluated until no internal syntax?
                - TODO Would it make sense to add a "Safe-mode" lane-gutter switch that would enable or disable "probable" safety checks like this, so a basic mistake wouldn't cause catastrophic meltdown while an advanced user could still say "I know what I asked for and give me exactly that". The evaluation still being subject to a maximum node-hits evaluation cap so it wouldn't lock up forever.

**Architecture**:
- Recursive parsing: When encountering a bounded token, recursively parse its content.
- Maintain parent-child relationships in the AST.

**Implementation**:
- Modify `parse_tokens` to handle nested parsing.
- Use the lexer internally for nested content if needed.

**Tests**:
- Test simple nested invocations (e.g., `<outer <inner>>`).
- Test mixed boundaries (e.g., `<{choice}>`).
- Test deeply nested structures.
- Validate tree structure and node relationships.

**Documentation**:
- Diagrams or examples of nested AST structures.
- Comments on recursion handling.

## Milestone 5: Unified Parser Integration
**Goal**: Integrate the parser with the unified lexer and update the engine interface.

**Features Implemented**:
- Modify `PromptEngine` to use the new parser instead of old dual-pipeline.
- Accept a single input string, lex it, then parse to AST.
- Update evaluation to traverse the AST.

**Architecture**:
- `PromptEngine` now: lex → parse → evaluate AST.
- Maintain backward compatibility where possible.
    - There is no backward to be compatible to, this is a fresh project from scratch.

**Implementation**:
- Update `macro_engine.py` to import and use `parser.py`.
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

**Features Implemented**:
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

**Features Implemented**:
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