# Milestone 1

## 4 Nesting
**Goal**: Support nested structures within invocation tokens.

**Features Implemented**:
- Parse nested tokens inside bounded tokens (e.g., `<outer <inner>>`).
- Create tree structures where `InvocationNode` can have child nodes.
- Handle multiple boundary types (`< >`, `{ }`).

**Architecture**:
- Recursive parsing: When encountering a bounded token, recursively parse its content.
- Maintain parent-child relationships in the AST.

**Implementation**:
- Modify `parse_token` to handle nested parsing.
- Use the lexer internally for nested content if needed.

**Tests**:
- Test simple nested invocations (e.g., `<outer <inner>>`).
- Test mixed boundaries (e.g., `<{choice}>`).
- Test deeply nested structures.
- Validate tree structure and node relationships.

**Documentation**:
- Diagrams or examples of nested AST structures.
- Comments on recursion handling.