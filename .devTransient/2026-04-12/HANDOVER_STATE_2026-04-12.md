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
  - **Leading `:` (Invalid Def)** -> It is inert data, essentially a bare Value without a Key. It is held locally for positional referencing.
- **AXIOM 2: Positional Mapping:** Positional digit invocations (`<0>`, `<1>`) strictly map to the Segment indices of the current Scope. `<0>` is always the Evaluated Key of Segment 0. `<1>` is the Evaluated Key of Segment 1 (or its Raw Value if it was Definition-coded).
- **AXIOM 3: Scope Equivalence (Scoped vs. Unscoped):** There is ZERO difference in how the internal payload of an Invocation is evaluated. The _only_ difference is the syntactic sugar:
  - **Unscoped (`<|Macro|...>`):** Signaled by a leading Split marker. Provides its Resolved Values' Definitions and AST Nodes to the Parent's Scope.
  - **Scoped (`<Macro|...>`):** Wrapped in a ScopeNode before processing. The internal definitions are popped and destroyed. The ScopeNode returns Literal Text to its parent.
- **AXIOM 4: JIT String Manipulation:** The exact order of operations for extracting Selection Modifiers (`$$`), parsing segments (`|`), and applying Option Selection is handled dynamically by the Evaluator during node execution, not hardcoded into the Lexer or Parser.

## 3. The Trap Ledger (Negative Constraints)

Previous iterations of this project fell into architectural traps. **Do not repeat them:**

- **TRAP: "Segment 0 is Special."** False. Segment 0 is not exceptional; it is just the first segment. Do not treat the first segment as "The Key" and the rest as "Arguments". They are all fundamentally Segments.
- **TRAP: "Empty Segment 0."** False. An Unscoped Invocation (`<|Macro>`) does not have an "empty Segment 0." It simply has a leading `|` token that triggers Unscoped injection behavior.
- **TRAP: "The Smart Parser."** False. The Parser does NOT split strings, extract modifiers, or apply logic. The Parser only maps Lexer Tokens to AST Node constructors. The Evaluator handles JIT tokenizing and string manipulation.
- **TRAP: "Evaluation = Resolution."** False. _Evaluating_ a string means running it through the engine to produce literal text. _Resolving_ a string means looking it up in the Context Stack Dictionary to find a matching Definition.

## 4. Pending TODOs & Next Steps

**Immediate Next Session Goals:**

1. **The Holistic Pipeline:** Draft the complete step-by-step internal logic for the pipeline phases, describing exactly how a raw string becomes final literal text using the Symmetrical Tree-Walk strategy (Expansion Phase on UnscopedInvocation Nodes, Execution Phase on Text/ScopedInvocation/Scope Nodes).
2. **Modifier / Syntax Ambiguities:** Define the exact JIT order of operations for how `$$` Modifiers interact with `|` Splits, Unscoped Invocations, and specifically how Modifiers apply to the _Resolved Values_ of Evaluated Keys.
3. **Document Updates:** Use the new Holistic Pipeline to rewrite `ARCHITECTURE_MANIFESTO.md` and `EVALUATOR_SPECIFICATION.md`.
4. **Trace Implementation Specs:** Define the exact schema for the PRNG Trace object (tracking Option Selection).
5. **Seed Pathing Specs:** Define the string manipulation logic for deterministic PRNG seed inheritance.
6. **"Frozen/Memoized" Randomization Feature (Design Stage):**
   - *The Problem:* By default, Lazy Evaluation causes randomized definitions (e.g., `:key:{A|B}`) to re-roll on every invocation due to PRNG seed mutation. We need a way to "freeze" a random selection for consistent re-use across a scope (e.g., rolling a character's name once).
   - *Current MVP Workaround:* Passing the group as a Positional Segment (e.g., `<Macro|{A|B}>`) forces evaluation before the child scope begins, keeping `<1>` consistent within that scope.
   - *Future Solution Breadcrumbs:* **Prior Thinking, Maybe Out-of-Date:** * Do NOT use True Eager Evaluation (evaluating during Hoisting): It breaks Order Independence (Footnotes) because required context may not be hoisted yet. Furthermore, appending options to an eagerly evaluated literal (e.g., `A` + `|C`) accidentally unfreezes it by creating a new PRNG split `A|C`.
      - Do NOT use Static PRNG Seeding: If the option pool is expanded via Append Definitions, a static seed applied to a larger pool might mathematically select a different item, causing the "frozen" value to spontaneously change mid-document.
      - *Recommended Exploration:* **Lazy Memoization.** A syntax flag (e.g., `:key|:val`) that keeps the Definition as Raw Text until its *first* Resolution. It evaluates using the fully realized Context, rolls the PRNG, and then caches/overwrites its own Value-Pattern in the Context Stack with the resulting Literal Text. This allows Append Definitions to safely expand the option pool *before* the first roll locks it.