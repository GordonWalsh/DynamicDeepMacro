# The Official Macro Engine Glossary

This document establishes the strict domain language for the Macro Engine. These terms must be used consistently across all specifications, code variables, and logic discussions to prevent semantic collisions.

## 1. The Syntax Tree & Hierarchy

- **1.1. AST Node:** An ephemeral, polymorphic object (`LiteralNode`, `GroupNode`, `InvocationNode`) that encapsulates the JIT logic to parse and evaluate a specific syntax pattern.
- **1.2. Parent / Child:** Relative structural terms. A Parent Node iterates over its Child Nodes during evaluation.
- **1.3. Top-Level:** Refers to syntax or text occurring at depth `0` relative to the current node's Payload, unhidden by any internal boundaries.
- **1.4. Scope:** The isolated temporal and spatial domain of an AST Node's execution lifecycle.
- **1.5. Token:** The atomic data unit produced by the Lexer. It contains a substring (retaining syntax), its bounding indices, and its structural type (e.g., `TokenType.INVOCATION`), but applies no semantic logic.

## 2. State & Determinism

- **2.1. Context Stack (The Context):** The dynamic `MacroContext` data structure passed down the tree. It holds the cumulative memory of active Definitions, the current PRNG Seed, and the Trace object.
- **2.2. Local Context:** Definitions owned directly by the current Scope.
- **2.3. Global Context:** Definitions inherited from the Context Stack prior to the current Scope's creation.
- **2.4. PRNG Seed:** A deterministic, path-dependent string used to calculate random rolls. Nodes modify inherited seeds predictably (e.g., appending an index like `_0` or `_2_Key`) before passing them to children, ensuring branch isolation.
- **2.5. Trace:** A tracking object within the Context that records how Options are selected at specific PRNG nodes for a given Seed. It allows users to query the decision-path of an evaluation after the string is fully generated.

## 3. Text States

- **3.1. Raw Text:** Unprocessed string data that may contain engine syntax (brackets, colons, splits) that must still be acted upon.
- **3.2. Literal Text:** Processed, inert string data. Any syntax characters within it are treated as plain text and will not be parsed by downstream engine processes.

## 4. Definitions, Keys & Dictionary

- **4.1. Definition:** The fundamental rule mapping a Key-Pattern to a Value-Pattern. It consists of structural properties (Strength, Position, Class) and its mapping logic. The term can refer to both the parsed data object and the raw string format.
- **4.2. Scope Hoisting:** The extraction of Definitions from a Payload so they can be injected into the active Scope. Most notably, this is the mechanism Unscoped Invocations use to elevate contained Definitions into acting as siblings of the Invocation itself.
- **4.3. Key-Pattern:** The left-hand side of a Definition. It can be a literal string or a regex search pattern.
- **4.4. Value-Pattern:** The right-hand side of a Definition. It is stored as Raw Text until it is successfully injected and evaluated.
- **4.5. Raw Key:** The unprocessed Raw Text of a Segment intended for dictionary lookup before it is evaluated.
- **4.6. Evaluated Key:** The Literal Text produced after evaluating a Raw Key. This is the exact string passed to the Context Stack to find a matching Key-Pattern.

## 5. Payloads, Groups, & Invocations

- **5.1. Payload:** The exact Raw Text residing inside an Invocation or Group's boundaries before it is tokenized or split.
- **5.2. Group:** A syntax structure (`{...}`) that evaluates its Payload in an isolated Child Scope, guaranteeing any internal Definitions do not escape into the Parent.
- **5.3. Scoped Invocation:** A syntax structure (`<...>`) without a leading split. It evaluates its Segments within an isolated Child Scope. The resulting Literal Text is provided to the Parent, while any internal Definitions are discarded and do not escape.
- **5.4. Unscoped Invocation:** A syntax structure (`<|...>`) signaled by a leading `SPLIT` token. It is evaluated without an isolated Child Scope; the Parent directly absorbs its hoisted Definitions and resulting Literal Text into the current scope.
- **5.5. Segments:** The Raw Text divisions created by Top-Level `SPLIT` (`|`) Tokens within any Payload (both Invocations and Groups). They are 0-indexed and uniformly equivalent in evaluation rules.
- **5.6. Selection Modifier:** The parsed logic derived from the `$$` syntax, containing the `Quantity`, `Indices`, and/or `Separator`.
- **5.7. Options:** The pool of Segments that are subjected to a Selection Modifier (or default PRNG behavior).
- **5.8. Selection:** The winning Option(s) remaining _after_ Option Selection, concatenated with any applicable Separator text.

## 6. Engine Processes

- **6.1. Lexing:** The single-pass process of converting Raw Text into a flat list of zero-depth Tokens.
- **6.2. Parsing:** The direct mapping of a Lexer Token to its corresponding AST Node constructor. It applies no recursive string logic itself.
- **6.3. Option Selection:** The process of applying a Selection Modifier to a pool of Options to yield the Selection.
- **6.4. Resolution (Dictionary Lookup):** The act of querying the Context Stack with an Evaluated Key to accumulate matching Value-Patterns.
- **6.5. Node Execution:** The JIT process where an AST Node prepares its Scope, executes its specific logic, processes its Children, and returns its final string.
- **6.6. String Evaluation:** The overarching recursive pipeline of passing a Raw Text string through Lexing, Parsing, and Node Execution to produce a final Literal Text string.
