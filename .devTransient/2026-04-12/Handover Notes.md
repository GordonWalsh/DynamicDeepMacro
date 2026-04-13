# Major Changes Since Lexer Implementation

**1\. Syntax & Semantics (The Unification of Segments)**

- **Segment Equivalence:** Inside an Invocation, all Segments are processed identically. Segment 0 is not a special "Key" field; it is just the first Segment.
- **The `:` Flag:** Instead of structural separation, the leading `:` determines behavior. No colon = Key-String (Resolves). Leading colon = Definition (Hoisted).
- **Scoped vs. Unscoped Equivalence:** The contents of `<Macro|...>` and `<|Macro|...>` are evaluated identically. The _only_ difference is whether the resulting output and definitions are returned as a Literal String to the parent, or injected directly into the Parent's Scope. (Triggered structurally by a leading `|` token).
- **Isolated Groups:** `{}` isolates evaluation into an independent child scope, ensuring its contents are fully resolved to a literal string before participating in the parent's syntax.

**2\. Architecture (The JIT Evaluator Pivot)**

- **Dumb Parser / Smart Evaluator:** We abandoned traditional rigid pipeline stages. The Parser simply turns Tokens into AST Node objects. The actual string manipulation (Tokenizing payloads, extracting modifiers, splitting segments) happens JIT inside the Evaluator's recursive loop.

- **The Two-Pass Scope Lifecycle:** To solve the "Footnote Architecture" (order independence), AST Nodes now evaluate in two phases:

1. _Expansion Pass:_ Lex/Parse the payload, hoist definitions, and resolve/inject any top-level Unscoped Invocations (`<|...>`).
2. _Execution Pass:_ Evaluate standard Scoped Invocations and construct the final literal string.

- **Resolution vs. Evaluation:** We strictly decoupled _Evaluating_ a string (processing raw syntax into literal text) from _Resolving_ a Key-String (looking up the literal text in the Context Stack to find matching Value-Patterns).

**3\. State Management**

- **Path-Dependent PRNG:** Randomization must be tied to a deterministic seed that mutates predictably based on tree depth and index, ensuring isolated sibling execution.
- **The Trace Object:** Added a requirement for a logging object to track PRNG selections for downstream visibility.

# Documentation Strategy for Handover

To ensure the next session inherits a clean, authoritative state, we need to organize the repository documents into three tiers:

**Tier 1: Finalized / Authoritative (Do Not Alter)**

- `LEXER_SPECIFICATION.md` & `lexer.py`
- `CORE_FEATURES_AND_BEHAVIORS.md` _(Create this from our v3 list)_
- `GLOSSARY.md` _(Create this from our v3 list, patching the Unscoped/Segment definitions)_

**Tier 2: Needs Significant Update (Rewrite in Next Session)**

- `ARCHITECTURE_MANIFESTO.md`: Must be updated to reflect the Two-Pass Scope Lifecycle and JIT AST Node evaluation.
- `PARSER_SPECIFICATION.md`: Needs to be stripped down to just the mapping of Lexer Tokens to `ASTNode` constructors.
- `EVALUATOR_SPECIFICATION.md`: Needs to define the JIT Tokenizing of Payloads and the Expansion vs. Execution passes.

**Tier 3: Handover Specific (Create Now)**

- `HANDOVER_AXIOMS.md` or `.txt`: A strictly formatted list of "Traps" and "Rules" to force into the LLM's system context immediately upon starting a new session.

# Deferred Topics and TODOs

1.  **Modifier Implementation:** How exactly is the `$$` syntax parsed into a `SelectionModifier` object, and how/when does it apply PRNG Option Selection to the Token/Segment list?
2.  **Trace Implementation:** What is the exact schema of the Trace object, and at what specific point in the JIT evaluation is the data captured?
3.  **PRNG Seed Pathing:** Define the exact string manipulation logic for ensuring deterministic seed inheritance (e.g., `ParentSeed -> ParentSeed_0`, `ParentSeed_1`).
4.  **Regex Integration:** Confirming the intersection of Positional Digits (`<0>`, `<1>`) with Regex Capture Groups during the Resolution phase.
5.  **Pre/Post Patterns:** Where exactly in the pipeline do `:<` and `:>` mutations occur relative to Lexing and the Two-Pass Scope?

# Special Prompts and Breadcrumbs

At the start of every session, and anytime you feel the LLM drifting, you paste a specific block:
`System Override: Acknowledge and adhere to the project axioms: 1. Segments are strictly equivalent. 2. Unscoped Invocations differ from Scoped ONLY in their injection target. 3. Evaluation and Resolution are strictly distinct steps. 4. Parser is dumb; Evaluator handles JIT Payload Lexing.`

Instruct the LLM in its initial prompt:
`Before answering architectural questions, you must output a <thought> block verifying your logic against GLOSSARY.md and HANDOVER_AXIOMS.md.`

Maintain a list of things not to do (e.g., "TRAP: Do not assume Segment 0 is special"). Negative constraints are highly effective breadcrumbs.

The Context Pruner (Session Handover Generator):
`We are preparing for a session hop. Based on our chat history, generate a comprehensive HANDOVER_STATE.md document. It must include: 1. The current confirmed architectural pipeline. 2. A 'Trap Ledger' listing previous misunderstandings or regressions that were corrected (to prevent the next LLM from repeating them). 3. The exact list of deferred TODOs. 4. The immediate next task for the new session.`

The Axiom Auditor (Early Session Validation):
`Act as a strict compliance checker. Review the provided documentation ([filename]) against our established Core Features and Glossary. Identify any instances where the text regresses to rejected concepts (e.g., Pipeline Parsing instead of JIT AST Parsing, Segment 0 Exceptionalism, or conflating Evaluation with Resolution). Output only the direct quotes of the violations and the reason they fail.`

```text
"We are continuing the development of a Python text-generation Macro Engine. Attached are the current project files. Please begin by reading `HANDOVER_STATE_2026-04-12.md`, `CORE_FEATURES_AND_BEHAVIORS.md`, and `GLOSSARY.md`.

To confirm you have internalized the state of the project, please output a `<thought>` block doing three things:

1.  Summarizing the difference between 'Evaluation' and 'Resolution'.
2.  Summarizing the 'Two-Pass Scope Lifecycle' and how it solves the 'Footnote Architecture' requirement.
3.  Confirming you understand the Universal Segment Equivalence axiom.
```
