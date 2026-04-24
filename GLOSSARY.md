# The Official Macro Engine Glossary

This document establishes the strict domain language for the Macro Engine. These terms must be used consistently across all specifications, code variables, and logic discussions to prevent semantic collisions.

## 1. The Syntax Tree & Hierarchy

- **1.1. AST Node:** An ephemeral, polymorphic object (eg, `TextNode`, `ScopeNode`, `ScopedInvocationNode`, `UnscopedInvocationNode`, `PositionalNode`). It represents any parsed structural element that requires further processing (from trivial `return`s to recursive walks).
- **1.2. Parent / Child:** Relative structural terms. A Parent Node iterates over its Child Invocations during Expansion and Child Nodes during Execution.
- **1.3. Top-Level:** Refers to syntax or text occurring at depth `0` relative to the current node's Payload, unhidden by any internal boundaries (eg, including direct text Definitions but not including those from Unscoped Invocations).
- **1.4. Scope:** The isolated temporal and spatial domain of an AST Node's Execution. Acts as a barrier to Child Nodes inadvertantly affecting the Parent, e.g. by leaking Definitions.
- **1.5. Token:** The atomic data unit produced by the Lexer. It contains a substring (retaining syntax), its bounding indices, and its structural type (e.g., `TokenType.INVOCATION`), but applies no semantic logic.
- **1.6. Eager Argument:** A segment preceded by `::` but lacking valid Definition syntax, explicitly evaluated into Literal Text before being stored, locking in PRNG results.
- **1.7. Lazy Argument:** A segment preceded by `:` but lacking valid Definition syntax stored as Raw Text, evaluated independently every time it is invoked.

## 2. State & Determinism

- **2.1. Context Stack (The Context):** The dynamic `MacroContext` data structure passed down the tree. It holds the cumulative memory of active Definitions, the current PRNG Seed, the Trace object, and a lightweight, ephemeral array of Literal Texts for `PositionalNode`s in the current Invocation frame.
- **2.2. Local Context:** Definitions owned directly by the current Scope, including those from Unscoped Invocations.
- **2.3. Global Context:** Definitions inherited from the Context Stack prior to the current Scope's creation.
- **2.4. PRNG Seed:** A deterministic, path-dependent string used to calculate random rolls. Inherited seeds are modified predictably (e.g., appending an index like `_0` or `_2_Key`) before being used by Children, ensuring branch isolation.
- **2.5. Trace:** A tracking object within the Context that records how Options are Selected. It allows users to query the decision-path of an Evaluation after the string is fully generated, without repeating the recursive walk. Details TBD.

## 3. Text States

- **3.1. Raw Text:** Unprocessed string data that may contain engine syntax (brackets, colons, splits) that must still be acted upon.
- **3.2. Literal Text:** Processed, inert string data. Any syntax characters within it are treated as plain text and will not be parsed by downstream engine processes.

## 4. Definitions, Keys & Dictionary

- **4.1. Definition:** The fundamental rule mapping a Key-Pattern to a Value-Pattern. It consists of structural properties (Strength, Position, Class) and its mapping logic. The term can refer to both the parsed data object and the raw string format.
- **4.2. Scope Hoisting:** The extraction of Definitions and Nodes from an Unscoped Invocation so they can be provided to the active Scope.
- **4.3. Key-Pattern:** The left-hand side of a Definition. It can be a literal string (Key-Patterns are not Evaluated) or a regex search pattern.
- **4.4. Value-Pattern:** The right-hand side of a Definition or the main text of an Argument (after leading `:`/`::`). If Lazy, it is stored as Raw Text until it is Invoked, and then Evaluated. If Eager, it is first Evaluated and then stored as Literal Text.
- **4.5. Raw Key:** The unprocessed Raw Text of a Segment intended for dictionary lookup, before it is Evaluated.
- **4.6. Evaluated Key:** The Literal Text produced after Evaluating a Raw Key. This is the exact string passed to the Context Stack to find matching Key-Patterns.

## 5. Payloads, Groups, & Invocations

- **5.1. Payload:** The exact Raw Text residing inside an Invocation or Group's boundaries before it is processed.
- **5.2. Group:** A syntax structure (`{...}`) that evaluates its Payload in an isolated Child `ScopeNode`, guaranteeing any internal Definitions do not escape into the Parent.
- **5.3. Scoped Invocation:** A syntax structure (`<...>`) without a leading `SPLIT` Token. It evaluates its Segments within an isolated Child `ScopeNode`. The resulting Literal Text is provided to the Parent during Execution, while any internal Definitions are discarded and do not escape.
- **5.4. Unscoped Invocation:** A syntax structure (`<|...>`) signaled by a leading `SPLIT` token. It is Expanded without an isolated Child Scope; the Parent directly absorbs its hoisted Definitions and resulting Literal Text into the current Scope.
- **5.5. Segments:** The Raw Text divisions created by Top-Level `SPLIT` (`|`) Tokens within any Payload (both Invocations and Groups). They are 0-indexed and processed uniformly, without special treatment of Segment 0.
- **5.6. Selection Modifier:** The parsed logic derived from the `$$` syntax, containing the `Quantity`, `Indices`, and/or `Separator`.
- **5.7. Options:** The pool of Segments that are subjected to a Selection Modifier (or default PRNG behavior).
- **5.8. Selection:** The process of turning the Option pool into a single data stream/object; or the winning Option(s) remaining *after* Option Selection, concatenated with any applicable Separator text.

## 6. Engine Processes

- **6.1. Lexing:** The single-pass process of converting Raw Text into a flat list of zero-depth Tokens.
- **6.2. Parsing:** The direct mapping of a Lexer Token to a corresponding code object (eg a Definition or AST Node). It applies no recursive string logic itself.
- **6.3. Option Selection:** The process of applying a Selection Modifier to a pool of Options to yield the Selection.
- **6.4. Resolution (Dictionary Lookup):** The act of querying the Context with an Evaluated Key to accumulate matching Value-Patterns, resulting in a concatenated Raw Text, or with a Positional index to retrieve the stored Value.
- **6.5. Expansion:** The recursive phase where Invocations are processed, with Unscoped Invocations adding their returned Definitions and AST Nodes to the Parent. Definitions are hoisted to a staging pool during this process to prevent cross-contamination between Sibling Invocations.
- **6.6. Node Execution:** The recursive JIT string generation phase where a Parent iterates over a finalized list of Child AST Nodes. The Parent applies Local Pre-Patterns to the Child Payloads (TODO may not be 100% correct re Invocations), then provides a complete Context Object with all necessary information for each Child to perform all applicable steps to complete its own Evaluation process. The Parent concatenates the resulting Literal strings from Children and applies Local Post-Patterns.
- **6.7. String Evaluation:** The holistic, overarching process of turning Raw Text into Literal Text. It encompasses Pre-Processing, Expansion, and Execution, as well as any other intermediate steps.
