The Core Architecture Manifesto: Macro Engine System Design
===========================================================

This document serves as the comprehensive, expert-level technical foundation for the Macro Engine. It details the system's structure, processing pipelines, and the strict architectural principles governing its operation. It explicitly documents not only the final design decisions but the specific compiler traps and logical paradoxes that necessitated them.

* * * *

1\. System Overview & The Eager/Lazy Paradigm
---------------------------------------------

The Macro Engine is a deterministic, context-aware, text-replacement compiler designed to handle highly nested, randomized structural logic. It operates on a strict three-subsystem pipeline: **Lexer → Parser → Evaluator**.

The foundational paradigm of the entire engine is **Breadth-Eager, Depth-Lazy Execution** (Just-In-Time Compilation).

-   **Breadth-Eager:** At any given execution step, the engine fully lexes and parses the flat, zero-depth layer of the current text payload into polymorphic objects.

-   **Depth-Lazy:** The engine absolutely *never* lexes, parses, or evaluates the internal contents of a macro or multi-value group until that specific branch has won a PRNG (Pseudo-Random Number Generator) roll and is actively invoked. Losing branches are discarded as raw strings, saving massive CPU cycles.

* * * *

2\. Phase A: Lexical Analysis (The Lexer)
-----------------------------------------

The Lexer converts raw strings into a flat list of `Token` objects. It is completely blind to execution logic, randomness, and context.

### Interval-Tracking Speculative Lexer

The Lexer operates in $O(N)$ linear time by avoiding Python string buffering (which is catastrophically slow due to immutability). Instead, it runs a single pass over the string, tracking the integer indices of start and end markers using independent pushdown automata (stacks) for each syntax type. String slicing happens exactly once at the end of the pass.

### Zero-Depth Interval Culling

To solve the paradox of malformed brackets (e.g., `< { > }`), the Lexer employs an interval culling algorithm.

-   **The Rule:** If a token boundary (like a `{ }` group or a `|` split) falls strictly within the registered bounds of a higher-order boundary (like a `< >` invocation), the inner marker is consumed and neutralized.

-   **The Result:** The Lexer only outputs top-level (zero-depth) tokens. Inner brackets remain inert literal text. This perfectly protects nested syntax and isolates user typos from destroying the entire document structure.

### Boundary vs. Discrete Tokenization

-   **Boundary Tokens (`< >`, `{ }`):** Require push/pop stacks to find matching ends.

-   **Discrete Tokens (`|`, `$$`):** Have no closing pairs. They are registered instantly at their string index, but are subject to the same Interval Culling rules to ensure they only act at the top level of the current scope.

* * * *

3\. Phase B: Parsing & Structural Generation (The Parser)
---------------------------------------------------------

The Parser acts as a Factory. It receives a flat list of zero-depth `Token` objects from the Lexer and maps them into a structural container.

### Polymorphic AST Generation (Avoiding Primitive Obsession)

**Trap Avoided:** *Leaving raw `Token` objects for the Evaluator to process procedurally.*

To keep the Evaluator lean, the Parser converts every execution token into a strongly typed subclass of a base `ASTNode`. Each node encapsulates its own execution logic via an `.evaluate(context)` method.

-   `LITERAL` tokens become `LiteralNode`s.

-   `INVOCATION` tokens become `InvocationNode`s.

-   `MULTI_VALUE` tokens become `MultiValueNode`s.

-   Everything is wrapped in a `BlockNode` representing the current scope.

### Scope Hoisting (The Footnote Architecture)

**Trap Avoided:** *Mutating global context during the parsing phase.*

Parsing is deterministic; evaluation is path-dependent (randomized). If the Parser pushed definitions to the global context while building the tree, discarded PRNG branches would leak state.

-   **The Solution:** The Parser cleanly separates State from Data. It identifies all `DEFINITION` tokens at the zero-depth level, converts them into standard Data Objects (not AST nodes), and stores them in a `local_definitions` list attached to the `BlockNode`.

-   This allows users to write massive blocks of variable definitions at the very bottom of their text (like footnotes); the Parser logically groups them so they are ready for the Evaluator, without prematurely executing them.

* * * *

4\. Phase C: State Management (The Context Stack)
-------------------------------------------------

The Context Stack is the memory engine. It is strictly a Search Engine and Data Store; it never executes AST logic.

### The LIFO Deque & Priority Queue

Definitions are scoped contextually. The stack uses a Double-Ended Queue (Deque):

-   **Strong Definitions (`:`):** Pushed to the HEAD (Left). Act as local overrides.

-   **Weak Definitions (`::`):** Pushed to the TAIL (Right). Act as global defaults.

### The Orthogonal Syntax Matrix

The engine completely decouples "When to apply" (Class) from "How to apply" (Action).

-   **Classes:** Bounded Macro (`:`), Unbounded Pre-Pattern (`:<`), Unbounded Post-Pattern (`:>`).

-   **Actions:** Base Terminator (`:` / `::`), Left-Concat (`<:`), Right-Concat (`>:`).

### The Search-Terminating Dual-Accumulator

**Trap Avoided:** *Using recursive definitions (`:key: <key> | val`) to build arrays.* Recursion forces the engine to eagerly collapse PRNG pools, destroying flat peer-to-peer data structures.

-   **The Solution:** Array building happens silently in the Context Stack search phase.

-   When a key is requested, the stack searches **Right-to-Left (Tail-to-Head / Weakest-to-Strongest)**.

-   It accumulates any Left-Concat (`<:`) or Right-Concat (`>:`) definitions it finds into a running list.

-   The exact moment it hits a Base definition (`:` or `::`), the search **terminates**, yielding the final ordered list. This natively resolves shadowing while allowing infinite, scoped list extensions.

### The Regex Identity Trap

**Trap Avoided:** *Allowing Unbounded Patterns (`:<`) to accumulate each other.*

Unlike Bounded Macros (which have explicit string keys), Unbounded Patterns are mathematical search rules. Attempting to concatenate regex replacements in the stack causes severe capture-group paradoxes.

-   **The Solution:** Context Stack accumulation strictly applies to Bounded Macros. For Unbounded Patterns, using a concat action (`<:` or `>:`) acts as an automated compiler shorthand that implicitly injects the regex `\g<0>` capture token to preserve the matched text, sparing the user from manual escape sequence hell.

* * * *

5\. Phase D: Evaluation & Execution (The Evaluator)
---------------------------------------------------

The Evaluator is the orchestrator. It receives a `BlockNode` and recursively calls `.evaluate()` down the tree, manipulating the Context Stack as it enters and exits scopes.

### Path-Hashed PRNG Determinism

To guarantee that a specific randomized prompt yields the exact same output every time a specific seed is used---even if the prompt is heavily branched---the random state cannot rely on a global counter.

-   Every time an `ASTNode` evaluates a child, it creates a unique seed for that child by hashing its own seed with the child's index (`Hash(parent_seed + "_child_0")`).

-   This perfectly isolates sibling tree branches. Modifying one part of a prompt will not butterfly-effect the random rolls of an unrelated branch.

### The Bounded Token Lifecycle (List Reduction)

The execution logic for an `InvocationNode` and a `MultiValueNode` is nearly identical, achieving massive code reuse. When evaluated, they execute this exact sequence:

1.  **Extraction:** Separate the modifier (`2$$`) from the payload.

        -   *Multi-Value:* Payload is the raw inline string.

        -   *Invocation:* Payload is retrieved via the Context Stack lookup.

2.  **Lexing:** Pass the payload string back to the Lexer to find zero-depth `SPLIT` tokens (`|`).

3.  **Bucketing:** Slice the resulting Token list into separate Option Buckets based on the splits.

4.  **Reduction:** Apply the modifier logic (e.g., pick 2 random buckets). **Destroy all other buckets.**

5.  **Recursive Parsing:** Pass the concatenated winning tokens to the Parser to build the child `ASTNode`s.

6.  **Execution:** Call `.evaluate()` on the new children.

**Trap Avoided:** *Splitting strings before Lexing.* Using Python's `.split('|')` would shatter nested syntax like `<Macro | param:val>`. The Lexer must identify the safe boundaries first.

**Trap Avoided:** *Eager Payload Flattening.* We initially considered eagerly resolving payloads to apply modifiers, but this broke nested hierarchical weights (`A | {B|C}`). Modifiers must be attached to the Invocation key directly (`<2$$key>`) so the engine only splits the top-level buckets, preserving the nested lazy hierarchy.

### The Inside-Out Concatenation Architecture

**Trap Avoided:** *Context Stack managing string buffers or sorting logic.*

When the Context Stack returns the list of concatenated definitions (from the Dual-Accumulator search), it returns them in the exact order they were searched (Strongest to Weakest, ending in the Base).

-   The Context Stack does **not** need to sort this list or manage left/right string buffers.

-   The Evaluator pops the Base, evaluates it, and then iterates through the rest of the list sequentially.

-   Because the strongest modifiers are processed first, they are concatenated directly against the Base string. Weaker modifiers are processed later, appending to the outer edges. This naturally builds the string from the **Inside-Out**, perfectly guaranteeing that Local Scope wraps tighter than Global Scope without any complex tracking overhead.

### The Anonymous Escape Block (Late Binding)

**Trap Avoided:** *Global Lexer rules for escape sequences (The Slash Collision Trap).* Applying `/ /` escape logic to all text destroys standard file paths and URLs.

-   **The Solution:** `/ /` delimiters are restricted entirely to Definition values (to explicitly separate regex from literal invocations).

-   To inject an inline escape sequence (like a newline), the engine uses Late-Binding. At the very end of an `InvocationNode`'s lifecycle---right before it queries the dictionary---it checks if the fully resolved key string starts and ends with `/` (e.g., `</\n/>`).

-   If true, it bypasses the Context Stack entirely, strips the slashes, decodes the Unicode escape natively, and returns the literal character. This allows escapes to be dynamically generated by macros while remaining perfectly sandboxed from standard text.

6\. Additional Technical Definitions & Paradigms
------------------------------------------------

This is the distilled, expert-level encapsulation of the engine's fundamental principles, derived directly from the architectural decisions made during our system design.

#### 1: Lexical Analysis Paradigms

*   **Interval-Tracking Speculative Lexer:** A zero-copy lexical scanner that records token boundaries as integer start/end pairs rather than buffering string slices, ensuring $O(N)$ linear time complexity.
*   **Zero-Depth Interval Culling:** The resolution algorithm that discards any registered token boundaries that fall strictly within the bounds of a higher-order hierarchy marker, safely neutralizing unbalanced brackets and natively protecting nested syntax.
*   **Boundary vs. Discrete Tokenization:** The distinction between paired contextual markers (< >, { }) which require pushdown-automata tracking, and zero-depth singular markers (|, $$) which are registered instantly.

#### 2: Parsing & Structural Paradigms

*   **Breadth-Eager / Depth-Lazy Parsing:** The engine eagerly builds a polymorphic AST for the current zero-depth scope, but strictly treats all nested macro/group contents as inert raw strings until explicitly invoked.
*   **Polymorphic AST Generation:** The parser functions as a Factory, mapping lexed tokens to strongly typed objects (LiteralNode, InvocationNode) that encapsulate their own evaluate(context) logic to prevent primitive-obsession in the Evaluator.
*   **Scope Hoisting (Footnote Architecture):** The structural decoupling of State (Definitions) from Data (Outputs) during parsing, allowing definitions to be position-independent within their block without mutating the global context pre-maturely.

#### 3: Execution & Evaluation Paradigms

*   **Lazy-Evaluation Recursion:** The fundamental guarantee that the Lexer and Parser are invoked _during_ the AST evaluation phase (just-in-time compilation), ensuring discarded PRNG branches consume zero parsing cycles.
*   **Path-Hashed PRNG Determinism:** The cryptographic state-tracking mechanism where a child node's random seed is deterministically computed by hashing the parent\_seed with the child\_index, isolating tree branches from sibling insertions/deletions.
*   **Inside-Out Scoped Concatenation:** The principle that nested tree modifiers apply strictly from the innermost scope outward, inherently prioritizing local scope tightly against the base string before applying global scope.
*   **Eager Payload Flattening:** The rule that a Multi-Value node or Invocation node must fully expand and flatten its payload into a raw literal string _before_ applying its own selection modifiers (e.g., 2$$).
*   **Late-Binding Escape Resolution:** The "Anonymous Escape Block" () acts at the very end of the .evaluate() lifecycle—replacing the dictionary lookup—allowing escape sequences to be computed dynamically via internal macros before bypassing the context stack.

#### 4: Context & State Management Paradigms

*   **LIFO Dual-Accumulator Context Deque:** The state engine architecture where definitions are pushed Strong-to-Head and Weak-to-Tail.
*   **Search-Terminating Accumulator Search:** The Context Stack lookup algorithm that traverses the deque Tail-to-Head (Strongest-to-Weakest), accumulating Left/Right directional definitions until it strikes a Base terminator, cleanly resolving shadowing and array extension.
*   **Orthogonal Syntax Matrix:** The complete decoupling of Pattern Class (Bounded :, Unbounded :>, :<) from Pattern Action (Base :, Append >:, <:), allowing fully combinatorial definition logic.
*   **Regex Identity Trap Avoidance:** The rule that Bounded Macros accumulate via exact string matching, while Unbounded Pre/Post Patterns are treated as discrete, non-accumulating sequential passes to prevent capture-group paradoxes.
*   **Shorthand Pattern Injection:** The automated AST behavior where applying directional accumulation (<:, >:) to an Unbounded Pattern implicitly injects the regex \\g<0> token, shielding the user from backreference syntax.