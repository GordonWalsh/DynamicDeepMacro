# SESSION HANDOVER & SYSTEM AXIOMS

**ATTENTION AI:** You are picking up a complex Python compiler project mid-stream. Before answering any prompts or writing any code, you MUST read this document, internalize the Project Context, memorize the Axioms, and review the Trap Ledger.

## 1. Project Context

We are building a dynamic, Just-In-Time (JIT), text-generation Macro Engine. It features deterministic pseudo-random number generation (PRNG), dynamic variable injection, and order-independent definition scoping ("Footnote Architecture").
It uses a Breadth-Eager, Depth-Lazy evaluation strategy. The engine parses flat text into a zero-depth AST, and string manipulation (tokenizing payloads, segment splitting, modifier extraction) happens JIT during the recursive evaluation loop, not in standard rigid compiler stages.

## 2. The Engine Axiom Ledger (Immutable Laws)

Your logic must strictly adhere to these axioms. Do not contradict them in specifications or code. You MUST use the exact terminology defined in `GLOSSARY.md`.

- **AXIOM 1: Universal Segment Equivalence:** Inside an Invocation (`<...>`), all Segments separated by `|` follow identical evaluation rules based purely on their leading character.
  - **No leading `:`** -> It is a Raw Key. It must be Evaluated and Resolved against the Context Stack.
  - **Leading `:` (Valid Def)** -> It is a Definition. It is hoisted into the local Scope.
  - **Leading `:` (Invalid Def)** -> It is inert data. It is held locally for positional referencing.
- **AXIOM 2: Positional Mapping:** Positional digit invocations (`<0>`, `<1>`) strictly map to the Segment indices of the current Scope. `<0>` is always the evaluated result of Segment 0. `<1>` is the evaluated result of Segment 1 (or its raw string if it was a definition).
- **AXIOM 3: Scope Equivalence (Scoped vs. Unscoped):** There is ZERO difference in how the internal payload of an Invocation is evaluated. The _only_ difference occurs at the start and end of the node's lifecycle:
  - **Scoped (`<Macro|...>`):** The local definitions are popped and destroyed. The node returns Literal Text to its parent.
  - **Unscoped (`<|Macro|...>`):** Signaled by a leading `|`. The node injects its hoisted definitions and its literal text directly into the Parent's scope.
- **AXIOM 4: JIT String Manipulation:** The exact order of operations for extracting Selection Modifiers (`$$`), parsing segments (`|`), and applying Option Selection is handled dynamically by the Evaluator during node execution, not hardcoded into the Lexer or Parser.

## 3. The Trap Ledger (Negative Constraints)

Previous iterations of this project fell into architectural traps. **Do not repeat them:**

- **TRAP: "Segment 0 is Special."** False. Segment 0 is not exceptional; it is just the first segment. Do not treat the first segment as "The Key" and the rest as "Arguments". They are all fundamentally Segments.
- **TRAP: "Empty Segment 0."** False. An Unscoped Invocation (`<|Macro>`) does not have an "empty Segment 0." It simply has a leading `|` token that triggers Unscoped injection behavior.
- **TRAP: "The Smart Parser."** False. The Parser does NOT split strings, extract modifiers, or apply logic. The Parser only maps Lexer Tokens to AST Node constructors. The Evaluator handles JIT tokenizing and string manipulation.
- **TRAP: "Evaluation = Resolution."** False. _Evaluating_ a string means running it through the engine to produce literal text. _Resolving_ a string means looking it up in the Context Stack Dictionary to find a matching Definition.

## 4. Pending TODOs & Next Steps

**Immediate Next Session Goals:**

1. **The Holistic Pipeline:** Draft the complete step-by-step information flow describing exactly how a raw string becomes final literal text, relying heavily on the new "Two-Pass Scope Lifecycle" (Expansion Pass vs. Execution Pass).
2. **Modifier / Syntax Ambiguities:** Define the exact JIT order of operations for how `$$` Modifiers interact with `|` Splits, Unscoped Invocations, and specifically how Modifiers apply to the _Resolved Values_ of Evaluated Keys.
3. **Document Updates:** Use the new Holistic Pipeline to rewrite `ARCHITECTURE_MANIFESTO.md` and `EVALUATOR_SPECIFICATION.md`.
4. **Trace Implementation Specs:** Define the exact schema for the PRNG Trace object (tracking Option Selection).
5. **Seed Pathing Specs:** Define the string manipulation logic for deterministic PRNG seed inheritance.
