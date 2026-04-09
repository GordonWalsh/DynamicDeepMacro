# Evaluator Specification

This document specifies the evaluation subsystem: recursive traversal and evaluation of Abstract Syntax Trees (ASTs) to produce final string output.

## Overview

The Evaluator performs the third stage of processing:
```text
Abstract Syntax Tree (AST) → [RECURSIVE EVALUATION] → Final String Output
```

The Evaluator's responsibilities are to:
1. Traverse the AST recursively (depth-first)
2. Manage definition scope (push/pop context stack)
3. Apply pattern substitutions (unbounded and bounded)
4. Resolve variable invocations
5. Compose results deterministically
6. Log trace state for secondary outputs

**See:** [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) for ASTNode, MacroContext, and evaluator state management.

---

## Seven-Phase Node Lifecycle

Each ASTNode evaluation follows a strict seven-phase lifecycle to ensure consistent ordering of effects.

### Phase 1: Push Local Arguments

**Action:** Parse and push local argument definitions to the context stack.

**Details:**
- Extract local arguments from node metadata (if present)
- For parameterized invocations: `<key|:arg:val>`
- Push both strong (`:`) and weak (`::`) definitions
- Return counts for scope cleanup in Phase 7

**Current Status:** Placeholder; returns (0, 0)

**Future:** Will support syntax like `<key|:arg:val>` for local scope arguments

---

### Phase 2: Apply Unbounded Pre-Patterns

**Action:** Apply PRE pattern substitutions to the raw text.

**Details:**
- Retrieve all DEFINITION nodes with `pattern_class='PRE'` from context stack
- Evaluate definitions left-to-right (strong first, then weak)
- Apply each definition to the entire text:
  - Literal key: string replacement
  - Regex key: regex matching
  - Regex value: regex substitution with backreferences
  - Literal value: literal replacement
- Accumulate results: each definition's output becomes the input for the next

**Ordering:** Pre-patterns are applied before any invocation parsing, allowing text transformations that affect boundary detection.

**Example:**
```text
Input: "dark sky with dark clouds"
Context: :<dark:bright
Result: "bright sky with bright clouds"
(then continues to Phase 3 with transformed text)
```

---

### Phase 3: Lex and Parse Bounded Tokens

**Action:** Identify and parse `< >` boundaries into child invocation nodes.

**Details:**
- Handled by lexer and parser functions
- Scan transformed text for `< >` boundaries
- For each boundary pair:
  - Extract content (may contain nested boundaries)
  - Create INVOCATION node with content as raw_text
  - Add to node's content_parts as child node
- Preserve literal text between boundaries

**Output:** content_parts now contains mixed literal strings and INVOCATION nodes

**Example:**
```text
Input (after Phase 2): "Generate a <adjective> <noun>"
Phase 3 Output: [
    "Generate a ",
    INVOCATION("<adjective>", raw_text="adjective"),
    " ",
    INVOCATION("<noun>", raw_text="noun")
]
```

---

### Phase 4: Recursively Evaluate Children and Concatenate

**Action:** Evaluate all child INVOCATION nodes and concatenate results with literal text.

**Details:**
- Iterate through content_parts left-to-right:
  - For literal strings: append directly to output
  - For INVOCATION nodes:
    - Recursively call evaluate() on child node
    - Append returned string to output
- Final result: complete text with all invocations resolved

**Scope Isolation:** Each child node gets its own context push/pop (Phase 1 and 7)
- Non-transparent child nodes do not leak definitions to siblings
- Transparent nodes (ROOT) do not create scope boundaries

**Example:**
```text
Input: [
    "Generate a ",
    INVOCATION(raw_text="adjective"),
    " ",
    INVOCATION(raw_text="noun")
]
Context: {adjective: "dark", noun: "wizard"}

Phase 4 Output:
  "Generate a " + "dark" + " " + "wizard" = "Generate a dark wizard"
```

---

### Phase 5: Apply Unbounded Post-Patterns

**Action:** Apply POST pattern substitutions to the concatenated text.

**Details:**
- Retrieve all DEFINITION nodes with `pattern_class='POST'` from context stack
- Evaluate definitions left-to-right (strong first, then weak)
- Apply each definition to the entire text (same as Phase 2)
- Accumulate results

**Ordering:** Post-patterns are applied after all invocation resolution, allowing final text cleanup.

**Example:**
```text
Input: "Generate a dark wizard"
Context: :>wizard:mage
Result: "Generate a dark mage"
```

---

### Phase 6: Pop Local Scope

**Action:** Remove locally-pushed definitions from context stack.

**Details:**
- Pop strong_count strong definitions (from Phase 1)
- Pop weak_count weak definitions (from Phase 1)
- Only for non-transparent nodes

**Current Status:** Placeholder; phase not yet implemented

**Invariant:** For every push in Phase 1, there must be a matching pop in Phase 6, to ensure siblings are isolated.

---

### Phase 7: Log Trace State

**Action:** Record evaluation results and state for secondary outputs.

**Details:**
- Log node identifier and final resolved value
- Log context state (definition counts, stack depth)
- Record execution metadata (timing, recursion depth)
- For ROOT node: aggregate all child logs

**Output:** Trace state dictionary for ComfyUI secondary outputs (secondary widgets, logs, etc.)

---

## Application of Unbounded Patterns

### Phase 2 & 5: Pattern Matching and Substitution

Unbounded patterns are applied sequentially to the full text using the following algorithm:

**For each Definition in priority order (left-to-right from context stack):**

1. **Determine pattern type:**
   - If `key_is_regex` and `value_is_regex`: regex key with regex value
   - If `key_is_regex` and not `value_is_regex`: regex key with literal value
   - If not `key_is_regex` and `value_is_regex`: literal key with regex value
   - If not `key_is_regex` and not `value_is_regex`: literal key with literal value

2. **Apply appropriate substitution:**

   **Regex Key + Regex Value:**

   ```python
   result = re.sub(definition.key, definition.value, text)
   ```

   Allows backreferences: `/(cat)/:feline \1` matches "cat" and replaces with "feline cat"

   **Regex Key + Literal Value:**

   ```python
   result = re.sub(definition.key, definition.value, text)
   ```

   Literal value is used as-is; escapes handled by regex engine

   **Literal Key + Regex Value:**
   ```python
   # Find all occurrences of literal key, replace with regex-evaluated value
   # Outsources handling of escape sequences and such to the regex engine
   # (Note: This is less common and may require custom implementation)
   result = custom_replace(definition.key, definition.value, text)
   ```

   **Literal Key + Literal Value:**
   ```python
   result = text.replace(definition.key, definition.value)
   ```
   Simple string replacement; all occurrences replaced

3. **Update text:** `text = result` for next iteration

**Key Principles:**
- Definitions are evaluated in **priority order** (strong before weak)
- Each definition's output becomes the input for the next
- Early definitions affect later definitions
- Creates a composition: `D1(D2(...Dn(input)...))`

### Example: Composed Substitutions

TODO Why not replace the `/  /  /` strings with definition syntax?
```text
Input: "The quick brown fox"

Context:
  strong D1: /quick/slow/      (regex)
  strong D2: /brown/gray/      (regex)
  weak   D3: /quick/fast/         (regex, fallback)

Evaluation:
  Step 1: "The quick brown fox" → (apply D1) → "The slow brown fox"
  Step 2: "The slow brown fox" → (apply D2) → "The slow gray fox"
  Step 3: "The slow gray fox" → (apply D3) → "The slow gray fox" (already replaced quick, so this step doesn't change the string)
  
Result: "The slow gray fox"
```

---
TODO Add description of other elements of context

## Context Stack Management

### MacroContext During Evaluation

The MacroContext is a double-ended deque that maintains definition priority during evaluation.

**Structure:**
```text
HEAD (strong, highest priority)
├─ Strong definitions (pushed in Phase 1)
├─ (evaluated left-to-right)
└─ (oldest strong definitions)

TAIL (weak, lower priority)
├─ Weak definitions (pushed in Phase 1)
├─ (oldest weak definitions at rightmost position)
└─ TAIL (weak, lowest priority)
```

**Evaluation Order:**
- Strong definitions at HEAD are checked first
- Weak definitions at TAIL are checked as fallback
- Within each strength category, **first pushed = last popped** (LIFO for strong, FIFO for weak)

### Scoping Rules

**Transparent Nodes:**
- Do not create scope boundaries
- Definitions pushed by children leak to siblings
- Allows global context to be shared

**Opaque Nodes:**
- Do create scope boundaries
- Definitions pushed in Phase 1 are popped in Phase 6
- Siblings do not see child definitions

**Example of Scope Isolation:**
```text
Input: "<noun_1> <noun_2>"
Context: {noun_1: "cat", noun_2: "dog"}

ROOT node (transparent):
  Phase 1: Push no local args
  Phase 3: Lex into [INVOCATION("<noun_1>"), " ", INVOCATION("<noun_2>")]
  Phase 4a: Evaluate INVOCATION("<noun_1>"):
    Phase 1: No local args
    Phase 3: Empty (no more boundaries)
    Phase 4: Resolve "noun_1" → "cat"
    Phase 5: Apply POST patterns
    Phase 6: No pops
    Result: "cat"
  
  Phase 4b: Evaluate INVOCATION("<noun_2>"):
    Phase 1: No local args
    Phase 3: Empty
    Phase 4: Resolve "noun_2" → "dog"
    Phase 5: Apply POST patterns
    Phase 6: No pops
    Result: "dog"
  
  Phase 4c: Concatenate: "cat dog"
  
Result: "cat dog"
```

---

## Invocation Resolution

When an INVOCATION node's raw_text is evaluated:

1. **Lookup:** Search context stack for a definition matching the raw_text
   TODO the strong-weak distinction naturally happens by how they are added, just search left-to-right
   - Strong definitions checked first (left-to-right)
   - Weak definitions checked as fallback
   - First match wins

2. **Apply BOUNDED Patterns:**
   - Retrieve all DEFINITION nodes with `pattern_class='BOUNDED'`
   - Apply to raw_text (same as Phases 2/5)

3. **Return:** The resolved value becomes the INVOCATION node's output

**Example:**
```text
Raw text: "adjective"
Context: 
  :adjective:dark        (strong definition)
  ::adjective:red        (weak definition, fallback)

Lookup process:
  Check strong definitions (left-to-right) → Found: "dark"
  
Result: "dark" (weak definition not checked)
```

---

## Determinism and Repeatability

The Evaluator ensures deterministic, repeatable execution:

### Principles

1. **Single-Pass Evaluation:** The AST is evaluated exactly once, top-to-bottom
2. **Order-Dependent:** Evaluation order (left-to-right, depth-first) determines outcome
3. **Context-Dependent:** Results depend on context state at evaluation time
4. **Path-Dependent PRNG:** (Future) Random selection keyed to evaluation path, not wall-clock time

### Guarantees

- Same AST + same context → **identical output** every time
- No non-deterministic operations (no random.random(), no time.time(), etc.)
- No multi-pass re-evaluation or delayed binding
- Stack trace can be reconstructed from context state + definition order

---

## Current Implementation Status

### Implemented in `macro_engine.py` TODO not any more

TODO evaluate will be a standalone function, with ASTNode.evaluate() just being a helper.
- **ASTNode.evaluate():** Core 7-phase lifecycle
  - Phase 1: Placeholder (no local args yet)
  - Phase 2: _apply_unbounded(text, 'PRE') fully implemented
  - Phase 3: _lex_string() with `< >` boundary parsing
  - Phase 4: Recursive child evaluation and concatenation
  - Phase 5: _apply_unbounded(text, 'POST') fully implemented
  - Phase 6: Placeholder (no scope pop yet)
  - Phase 7: Partial (trace logging not yet implemented)

- **ASTNode._apply_unbounded():** Pattern substitution engine
  - Regex key with regex value: `re.sub(key, value, text)`
  - Literal key with literal value: `text.replace(key, value)`
  - Proper escaping for regex patterns
  - Composition of multiple patterns

- **MacroContext:** Context stack management
  - Deque-based with strong at HEAD, weak at TAIL
  - push(), pop_strong(), pop_weak(), get_definitions()
  - Left-to-right traversal for priority ordering

### Not Yet Implemented

- Parameterized invocations: `<key|:arg:val>` (Phase 1)
- Local scope pop logic (Phase 6)
- Trace state logging (Phase 7)
- Transparent node support
- DEFINITION node type handling
- `$$` parameter expansion
- Multi-boundary evaluation (`{ }`, `[ ]`)

---

## Related Documentation

- [CORE_TYPES_AND_INTERFACES.md](CORE_TYPES_AND_INTERFACES.md) - ASTNode and MacroContext specifications
- [LEXER_SPECIFICATION.md](LEXER_SPECIFICATION.md) - String → Token lexing
- [PARSER_SPECIFICATION.md](PARSER_SPECIFICATION.md) - Token → AST parsing
- [UNIFIED_PROCESS_PLAN.md](UNIFIED_PROCESS_PLAN.md) - Architecture strategy and rationale
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Project context and agent guidelines
