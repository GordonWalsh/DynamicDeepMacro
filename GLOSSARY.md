# The Official Macro Engine Glossary

This document establishes the strict domain language for the Macro Engine. These terms must be used consistently across all specifications, code variables, and logic discussions to prevent semantic collisions.
TODO 2026-05-15: This document needs to be reviewed following pipeline updates ~~and optimizations to `Token`s~~. (I think )

## 1. The Syntax Tree & Hierarchy

- **1.1: AST Node:** An ephemeral, polymorphic object (eg, `TextNode`, `ScopeNode`, `ScopedInvocationNode`, `UnscopedInvocationNode`, `PositionalNode`). It represents any parsed structural element that requires further processing (from trivial `return`s to recursive walks).
- **1.2: Parent / Child:** Relative structural terms. A Parent Node iterates over its Child Invocations during Expansion and Child Nodes during Execution.
- **1.3: Top-Level:** Refers to syntax or text occurring at depth `0` relative to the current node's Payload, unhidden by any internal boundaries (eg, including direct text Definitions but not including those from Unscoped Invocations).
- **1.4: Scope:** The isolated temporal and spatial domain of an AST Node's Execution. Acts as a barrier to Child Nodes inadvertantly affecting the Parent, e.g. by leaking Definitions.
- **1.5: Token:** A Lazy representation of a chunk of sliced, labelled text. It contains a referenced root string, its bounding indices, and its structural type (e.g., `TokenType.SCOPE`), but applies no semantic logic.
- **1.6: Eager Argument:** A segment preceded by `::` but lacking valid Definition syntax, explicitly evaluated into Literal Text before being stored, locking in PRNG results.
- **1.7: Lazy Argument:** A segment preceded by `:` but lacking valid Definition syntax stored as Raw Text, evaluated independently every time it is invoked.
- **1.8: -oid:** A suffix for Token types (e.g. `TEXTOID`, `INVOCATIONOID`, `DEFINITIONOID`) indicating an incompletely indentified structure, one with ambiguous specific type (e.g. Unscoped vs scoped Invocation), or one having partial structural alignment but not full agreement with the generalized label (e.g. Arguments and Definitions may collectively route into a Definitionoid path at some point)

## 2. State & Determinism

- **2.1: Context Stack (The Context):** The dynamic `MacroContext` data structure passed down the tree. It holds the cumulative memory of active Definitions, the current PRNG Seed, the Trace object, and a lightweight, ephemeral array of Literal Texts for `PositionalNode`s in the current Invocation frame.
- **2.2: Local Context:** Definitions owned directly by the current Scope, including those from Unscoped Invocations.
- **2.3: Global Context:** Definitions inherited from the Context Stack prior to the current Scope's creation.
- **2.4: PRNG Seed:** A deterministic, path-dependent string used to calculate random rolls. Inherited seeds are modified predictably (e.g., appending an index like `_0` or `_2_Key`) before being used by Children, ensuring branch isolation.
- **2.5: Trace:** A tracking object within the Context that records how Options are Selected. It allows users to query the decision-path of an Evaluation after the string is fully generated, without repeating the recursive walk. Details TBD.

## 3. Text States

- **3.1: Raw Text:** Unevaluated geometry. This is a direct slice of the original input string as identified by the Lexer. It is assumed to contain active instructions/syntax until proven otherwise by the Evaluator.
- **3.2: Literal Text:** Text that has been reduced to **Normal Form**, containing no further actionable syntax. It is not considered inert, just currently exhausted of instruction. It is the result of an Eager Evaluation phase or the Lexer identifying a slice as without syntax. If Literal Text is later modified or combined with other text, it reverts bsck to the Raw state.
- **3.3: Escape Text:** Text explicitly wrapped in `</.../>` to indicate a persistent instruction to not process the contents. Escape markers are _never_ consumed by the Parser or AST Nodes; they survive in the text indefinitely, shielding the contents from the engine no matter the number of recursions or substitutions that occur. They are only removed in a final cleanup pass just before handing the generated string back into user space.
- **3.4: Payload:** Raw unprocessed string content of an object, stripped of its outer syntax boundaries (e.g., the text inside `< >` for an Invocation, the literal string of a TextNode, the raw Value-Pattern of a Definition, the text represented by a Token, etc.).
- **3.5: Resolved Value:** Final string returned after the engine processes a Key-String against the Context (including concatenation of Definitions, array indexing, and Regex substitutions), but before beginning to Evaluate it as Raw Text.

## 4. Definitions, Keys & Library

- **4.1: Definition:** The fundamental rule mapping a Key-Pattern to a Value-Pattern. It consists of inherent structural properties (Position, Class), its ingestion behavior (Strength, Eagerness) and its Key and Value mapping logic. The term can refer to both the parsed data object and the raw string format.
- **4.2: Scope Hoisting:** The extraction of Definitions and Nodes from an Unscoped Invocation so they can be provided to the active Scope.
- **4.3: Key-Pattern:** The left-hand side of a Definition. It can be a literal string (Key-Patterns are not Evaluated) or a regex search pattern.
- **4.4: Value-Pattern:** The right-hand side of a Definition or the main text of an Argument (after leading `:`/`::`). If Lazy, it is stored as Raw Text until it is Invoked, and then Evaluated. If Eager, it is first Evaluated and then stored as Literal Text.
- **4.5: Raw Key:** The unprocessed Raw Text of a Segment intended for dictionary lookup, before it is Evaluated.
- **4.6: Evaluated Key:** The Literal Text produced after Evaluating a Raw Key. This is the exact string passed to the Context Stack to find matching Key-Patterns.
- **4.7: Definition Library:** The structure holding ordered collections of Definitions and providing the necessary functions to query those Definitions or get a relevant subset of them.

## 5. Groups, & Invocations

- **5.1: Group:** A syntax structure (`{...}`) that evaluates its Payload in an isolated Child `ScopeNode`, guaranteeing any internal Definitions do not escape into the Parent.
- **5.2: Scoped Invocation:** A syntax structure (`<...>`) without a leading `SPLIT` Token. It evaluates its Segments within an isolated Child `ScopeNode`. The resulting Literal Text is provided to the Parent during Execution, while any internal Definitions are discarded and do not escape.
- **5.3: Unscoped Invocation:** A syntax structure (`<|...>`) signaled by a leading `SPLIT` token. It is Expanded without an isolated Child Scope; the Parent directly absorbs its hoisted Definitions and resulting Literal Text into the current Scope.
- **5.4: Positional Invocation:** A syntax structure (`<1>`) of a single digit inside of Invocation wrapping. It is a reference to the Segments of the Invocation containing the Positional Invocation.
- **5.5: Segments:** The Raw Text divisions created by Top-Level `SPLIT` (`|`) Tokens within any Payload (both Invocations and Groups). They are 0-indexed and processed uniformly, without special treatment of Segment 0.
- **5.6: Selection Modifier:** The parsed logic derived from the `$$` syntax, containing the `Quantity`, `Indices`, and/or `Separator`.
- **5.7: Options:** The pool of Segments that are subjected to a Selection Modifier (or default PRNG behavior).
- **5.8: Selection:** The process of turning the Option pool into a single data stream/object; or the winning Option(s) remaining _after_ Option Selection, concatenated with any applicable Separator text.

## 6. Engine Processes

TODO: Update these, and possibly add new items to reflect the evolved pipeline.

- **6.1: Lexing:** The process of converting Raw Text into a flat list of zero-depth Tokens.
- **6.2: Parsing:** The direct mapping of a Node-generating Token to a corresponding Node object. It applies no recursive string logic itself.
- **6.2: Definition Handling:** The processing of a Definition Token into a populated Definition object that is sent to the appropriate internal container of a Definition Library.
- **6.3: Option Selection:** The process of applying a Selection Modifier to a pool of Options to yield the Selection.
- **6.4: Resolution (Dictionary Lookup):** The act of querying the Context with an Evaluated Key to accumulate matching Value-Patterns, resulting in a concatenated Raw Text, or with a Positional index to retrieve the stored Value.
- **6.5: Expansion:** The recursive phase where Invocations are processed, with Unscoped Invocations adding their returned Definitions and AST Nodes to the Parent. Definitions are hoisted to a staging pool during this process to prevent cross-contamination between Sibling Invocations.
- **6.6: Node Execution:** The recursive JIT string generation phase where a Parent iterates over a finalized list of Child AST Nodes. The Parent applies Local Pre-Patterns to the Child Payloads (TODO may not be 100% correct re Invocations), then provides a complete Context Object with all necessary information for each Child to perform all applicable steps to complete its own overarching string Evaluation process. The Parent concatenates the resulting Literal strings from Children and applies Local Post-Patterns.
- **6.7: String Evaluation:** The holistic, overarching process of turning Raw Text into Literal Text. It encompasses Pre-Processing, Expansion, and Execution, as well as any other intermediate steps.

- **Footnote Architecture:** The requirement that definitions are order-independent within a block. A definition at the bottom of a payload correctly applies to an invocation at the top.
