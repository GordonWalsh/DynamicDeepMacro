# GitHub Copilot & AI Agent Instructions

## 1. Project Context & Copilot Instructions
You are assisting with the development of a high-performance **Macro Compiler and Text Expansion Engine** built as a custom node suite for **ComfyUI**. 

The engine uses a custom Orthogonal Syntax Matrix to parse, evaluate, and inject variables into generative AI prompts. It operates via an Abstract Syntax Tree (AST), a Double-Ended Context Stack, and a path-dependent deterministic PRNG.

**Current Implementation Status:** The core engine is implemented in `macro_engine.py` as a Python module with unit tests in `test_suite.py`. ComfyUI integration is planned but not yet implemented.

**Unified Parsing Architecture (Future):** The engine currently treats global context definitions and prompt text as separate inputs, but they should be unified into a single parsing pipeline. Both are subject to the same definition syntax and escaping rules. The roadmap is to merge `_parse_global_context` and `_lex_string` into a single character-by-character lexer that produces a mixed AST containing definition nodes and literal/invocation nodes, allowing definitions to appear anywhere in the input stream and creating true local scoping where definitions pushed during evaluation of one subtree do not leak to siblings unless the parent node is transparent.

**Core Directives for AI Agents:**
* Prioritize deterministic execution. Generative AI prompts require exact repeatability based on seed and tree path.
* Do not attempt to use `re.sub` or raw Regex to parse Bounded Tokens (`< >`, `{ }`). You must use the custom Pushdown Automaton / character-by-character Lexer to prevent nesting failures.
* Maintain the strict separation between **State** (the Context Stack) and **Output** (the Return Buffer/Trace State Object). Do not allow literal text to leak into the definition contexts.
* When writing test cases, use raw strings (e.g., `r"string"`) for any strings containing regex patterns or escape sequences to avoid unintended Python string interpretation.
* Ensure syntax elements (e.g., `:`, `< >`, `/ /`) are not surrounded by extraneous whitespace in test strings or context definitions, as the parser is sensitive to exact formatting.
* For regex patterns in definitions, wrap both key and value in `/ /` if they contain regex syntax; use escape characters only for syntax markers, not arbitrary backslashes.
* When adding new tests, enable debug mode in `generate()` calls until the test passes to inspect stack and trace logs.
* Only unescape characters that are part of the defined syntax (e.g., `\` before `:`, `<`, `>`, `/`); do not arbitrarily skip backslashed characters outside of syntax.

---

## 2. Conventions and Behaviors to Preserve
When generating or refactoring code, adhere strictly to these architectural constraints:

### Scope & Stack Management
* **The Double-Ended Context Stack:** State definitions are managed in a `deque`.
  * Strong Definitions (`:`) push to the **Head** (Left).
  * Weak Definitions / Defaults (`::`) push to the **Tail** (Right).
* **Left-to-Right Traversal:** When searching for a variable definition, iterate forward through the context stack (normal order), ensuring Strong/local definitions are checked before Weak/global defaults.
* **Lexical Scoping:** Always push local scope markers/definitions when entering an AST node, and strictly `pop()` them when exiting, *unless* the node is invoked transparently (e.g., the `<|<Macro>>` Dummy Root).

### Execution Phasing
An AST Node lifecycle must strictly follow this order:
1. Push local arguments to Context.
2. Apply Unbounded Pre-Patterns (execute Left-to-Right on the string, pulling patterns left-to-right from the stack in evaluation order).
3. Resolve Multi-Value sequences (`{a|b|c}`, `$$` logic).
4. Lex and Parse Bounded Tokens (`< >`) into child AST nodes.
5. Recursively evaluate children and concatenate literal text.
6. Apply Unbounded Post-Patterns (Left-to-Right on the string, left-to-right evaluation from the stack).
7. Pop local scope.

### The Trace State Object
* Never implement multi-pass evaluation for secondary variables.
* The Root AST evaluates exactly once. Every bounded node resolution must be logged to a global `Trace State Dict`. Secondary ComfyUI outputs merely perform dictionary lookups against this trace.

---

## 3. Integration Notes (ComfyUI Specifics)
* **Node Mappings:** Ensure all classes are properly registered in `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.
* **String Inputs:** Assume ComfyUI `STRING` widgets with `multiline=True`. Handle `\n` and `\r\n` safely during lexing.
* **Escape Characters:** The escape character (default `\`) should be pulled from node properties. Ensure it protects syntax markers during lexing and is stripped from the final Text Encode output.
* **LoRA Stripping:** Ensure `[group: <lora:...>]` wrappers are stripped before final output, as ComfyUI's native backend will throw errors on custom wrappers.

---

## 4. Top-Level Tasks for New PRs
When generating code for a new Pull Request, verify the following:
1. **Implement missing parser parts in `macro_engine.py`:**
   - `_parse_global_context` (context string syntax `:<`, `:`, `:>`).
   - `_lex_string` to return tokens+ASTNodes for `<...>` and `{...}` patterns.
   - `_push_local_args` to convert `<key|arg:val>` into context pushes.
2. **Keep behavior consistent with existing tests in `test_suite.py`** (`strong_shadowing`, `weak_defaults`, `lexical_scoping_isolation`, `transparent_dummy_root`, `unbounded_execution_order`).
3. **Lexer Robustness:** Does the Lexer handle escaped characters, malformed brackets (e.g., `< { > }`), and nested macros without catastrophic backtracking?
4. **Infinite Recursion Protection:** Is the global `MAX_EVAL_DEPTH` (or max node visit count) implemented to prevent stack overflows?

## 5. Workflow Commands
- Run tests from repo root: `python test_suite.py`
- Keep test assertions precise (no partial/magic string expectations unless explicit semantic intent).

## 6. What to Explain in Code Comments
- Explain each source of scoping effects (strong vs weak vs transparent) in `MacroContext` and `ASTNode._push_local_args` maps.
- Document the expected `context_string` grammar in `_parse_global_context` for future maintainers.

## 7. When to Ask for Human Input
- If behavior for nested conflicting regex substitution matches is unclear, ask for desired precedence (current test implies strong def wins in left-to-right stack order).
- If converting this to production, clarify the placeholder in `_lex_string` must become stack-based balanced-delimiter parser.