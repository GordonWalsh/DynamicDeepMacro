# HANDOVER_UPDATE.md

## 1. Verified Facts, Corrections, and System Rules (User Approved)

### Terminology and Definitions

- **Capitalization Rule:** Capitalized words (e.g., _Evaluation_, _Definition_, _Scope_, _Token_) strictly refer to their specific definitions in `GLOSSARY.md`. Uncapitalized words use their standard conversational English meaning.
- **Payload vs. Resolved Value:** The _Payload_ is the raw text contained within an Invocation or Group (e.g., the text inside `< >`). The _Resolved Value_ is the string returned _after_ applying a Definition/dictionary lookup. They are distinct concepts.
- **Evaluation vs. Execution:** We _Execute_ AST Nodes (which corresponds to calling the `.execute()` method on them). _Evaluation_ refers to the overarching string-processing pipeline, not the action performed on individual parsed nodes.
- **Universal Segment Equivalence (Axiom 1):** This axiom dictates that inside a single Invocation, all 0-indexed Segments separated by `|` follow identical evaluation rules based purely on their leading character. Segment 0 is not a special "primary" key; all are treated uniformly. This axiom is _not_ a comparison between Scoped and Unscoped Invocations.

### Scope and AST Lifecycle

- **Scope Management Timing:** Scope lifecycle is tied to the Node Execution loop, not the beginning of the string parsing phase. When looping over node Executions, the flow must be: push a Scope Sentinel -> Execute the Child Node -> pop back to the Sentinel.
- **Unscoped Invocation Expansion:** Top-Level Unscoped Invocations must undergo their Phase 1 recursive expansion **independently** of other Top-Level Sibling Unscoped Invocations. Their resulting Definitions cannot be naively injected into the Parent Context during a left-to-right walk, as this would alter the context for siblings. The Unscoped Invocations must either cache their definitions in a separate pool or be kept encapsulated until every sibling Unscoped Invocation has been explored, only being hoisted afterward.
- **Unscoped AST Flattening:** After Unscoped Invocations are independently expanded, their resulting Child Nodes are flattened into the Parent's AST list to be Executed alongside the Parent's other Children.

### Modifiers and Option Selection

- **Separator Handling:** Separators extracted from Selection Modifiers (e.g., the `,` in `2$$,$$`) are treated as Raw Text. They are Lexed independently into a Token list, and that list is interleaved between the Selected Option sub-lists.
- **Modifier Application:** The Modifier found in a Segment of an Invocation applies to the _Resolved Value_ of that Key-String, not the Key-String itself. It acts as the Initial Selection Modifier for that Resolved Value when it is evaluated.

### The "Applied-Once" Pattern Principle

- Every piece of text should be affected by each applicable Pre-Pattern and Post-Pattern exactly once.
- **Local Pre-Patterns on Children:** The Parent applies its own Local Pre-Patterns to the Payloads of its Child Nodes _before_ the Child Nodes are Executed. The Child cannot do this itself because it cannot distinguish between the Parent's Local Pre-Patterns and inherited Grandparent Pre-Patterns.
- **Pre-Patterns on Resolved Values:** The Value Text of Invoked Definitions appears completely Raw to the system. Therefore, the _entire stack_ of inherited and local Pre-Patterns should be applied to the Resolved Value before further processing.
- **Local Post-Patterns:** Applied bottom-up. A Scope applies _only_ its Local Post-Patterns to the concatenated Literal Text resulting from its execution _before_ returning that Literal string to the Parent.

---

## 2. Identified AI Errors and Source Misinterpretations

- **Error: Conflating "Evaluation" with "Node Execution" and "Payload" with "Resolved Value".**
  - _Source of Error:_ Abstractly generalizing the engine's text processing instead of adhering strictly to the `GLOSSARY.md` definitions. I treated any string being processed as a "payload," missing the crucial architectural distinction between parsing user input and processing a dictionary lookup result.
- **Error: Describing Axiom 1 as a rule differentiating Scoped from Unscoped Invocations.**
  - _Source of Error:_ Misinterpreting a note in the `HANDOVER_STATE_2026-04-12.md` Trap Ledger ("Unscoped Invocation... does not have an 'empty Segment 0'") and blending it with Axiom 1, completely losing the actual meaning of Universal Segment Equivalence.
- **Error: Creating Scope as "Step 1" of the Phase 1 Pipeline.**
  - _Source of Error:_ Attempting to neatly package Scope Expansion and Token Parsing into a single top-to-bottom block. This fundamentally broke the isolation rule required for Sibling Unscoped Invocations, which must execute in the exact same inherited context before mutating anything.
- **Error: Attempting to have Child Nodes apply the Parent's Local Pre-Patterns.**
  - _Source of Error:_ Trying to solve the "Pre-Pattern Paradox" (where Local Pre-Patterns can't apply to their own block before Lexing) by delegating it to the child payload. I failed to logically trace how the `Context Stack` works—a child has no built-in way to identify the "boundary" of the Parent's local layer within the inherited stack.
- **Error: "Black-boxing" Segment Resolution.**
  - _Source of Error:_ Attempting to simplify a massive pipeline by ignoring the exact operational order of Segment Resolution, Modifiers, and Separators. This resulted in an incomplete and useless conceptual model.

---

## 3. Instructions for the Next AI Agent

1. **Do Not Generate Monolithic Pipelines:** Break down the architecture into smaller, distinct steps (e.g., Node Entry, Lexing, Invocation Resolution, Selection, Token Parsing, Node Execution). Solve and verify the information states _between_ these steps individually before trying to stitch them together.
2. **Respect Glossary Capitalization:** If the user capitalizes a word (e.g., _Scope_, _Token_, _Evaluation_), you must treat it strictly as the defined entity from `GLOSSARY.md`. Do not use these words casually.
3. **Strictly Maintain Unscoped Independence:** When detailing Phase 1 (List Construction/Expansion), ensure that Top-Level Unscoped Invocations are expanded using the baseline inherited context. Do not let their hoisted Definitions leak into the context used to expand their siblings.
4. **Tie Scope to Execution, Not Parsing:** Enforce Scope transitions (pushing/popping a Sentinel) specifically around the step where a Child Node is Executed, unifying the handling of Text nodes, Group nodes, and Invocations.
5. **Enforce the Applied-Once Principle:** Route Pre-Patterns carefully. Ensure you clearly state that the _Parent_ mutates the child's payload with its Local Pre-Patterns, while _Resolved Values_ from Dictionary lookups receive the entire Context Stack's Pre-Patterns.
6. **Track Modifiers and Separators Precisely:** Do not gloss over how Modifiers flow from an Invocation Segment down into the execution of a Resolved Value. Track exactly when a Separator string is isolated, lexed, and interleaved.```
