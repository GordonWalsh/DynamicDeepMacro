# The Core Architecture Manifesto: Macro Engine System Design

This document serves as the comprehensive, expert-level technical foundation for the Macro Engine. It details the system's structure, processing pipelines, and the strict architectural principles governing its operation. It explicitly documents not only the final design decisions but the specific compiler traps and logical paradoxes that necessitated them.

-----

## 1\. System Overview & The Eager/Lazy Paradigm

The Macro Engine is a deterministic, context-aware, text-replacement compiler designed to handle highly nested, randomized structural logic. The Macro Engine operates on a phased Evaluation Pipeline: Pre-Processing (i.e. `LexAndSegment`) -> Expansion (Invocation Resolution & Hoisting) -> Execution (Scope Management & Generative Concatenation).".

The foundational paradigm of the entire engine is **Breadth-Eager, Depth-Lazy Execution** (Just-In-Time Compilation), executed across a Unified AST using Symmetrical Passes:
  - **Expansion:** A recursive tree-walk targeting `UnscopedInvocationNode`s to resolve them into Definitions and flat Nodes.
  - **Execution:** A recursive tree-walk targeting `TextNode`s, `ScopeNode`s, and `ScopedInvocationNode`s to concatenate them into Literal Strings.
  - **Breadth-Eager:** At any given step, the engine fully Lexes and Parses the flat, zero-depth layer of the current text Payload into polymorphic objects.
  - **Depth-Lazy:** The engine never Parses or Evaluates the internal contents of a macro or multi-Segment Group until that specific branch is Selected by the PRNG (Pseudo-Random Number Generator). Losing branches are discarded early, saving CPU cycles.

### Functional Composition & AST Avoidance

The engine prevents AST depth-bloat through Functional Composition rather than literal object wrapping. A Scoped Invocation `<A|B>` is not parsed as a `ScopeNode` containing an `InvocationNode`. Instead, the Parser outputs a distinct `ScopedInvocationNode`. During processing, this node simply calls the shared Scope Node Processing function wrapped around the Invocation Processing function.
Similarly, Positional Digits (`<0>`) avoid injecting massive overhead into the main Definition dictionary by mapping to a dedicated, ephemeral `positionals` array on the Context. The Parser outputs a `PositionalNode`, which inherently holds completed Literal Text and entirely skips standard `InvocationNode` logic.

-----

## 2\. Phase A: Lexical Analysis (The Lexer)

The Lexer converts raw strings into a flat list of `Token` objects. It is completely blind to execution logic, randomness, and context.

### Interval-Tracking Speculative Lexer

The Lexer operates in $O(N)$ linear time by avoiding Python string buffering (which is catastrophically slow due to immutability). Instead, it runs a single pass over the string, tracking the integer indices of start and end markers using independent pushdown automata (stacks) for each syntax type. String slicing happens exactly once at the end of the pass.

### Zero-Depth Interval Culling

To solve the paradox of malformed brackets (e.g., `< { > }`), the Lexer employs an interval culling algorithm.

- **The Rule:** If a token boundary (like a `{ }` group or a `|` split) falls strictly within the registered bounds of a higher-order boundary (like a `< >` invocation), the inner marker is consumed and neutralized.

- **The Result:** The Lexer only outputs top-level (zero-depth) tokens. Inner brackets remain inert literal text. This perfectly protects nested syntax and isolates user typos from destroying the entire document structure.

### Boundary vs. Discrete Tokenization

- **Boundary Tokens (`< >`, `{ }`):** Require push/pop stacks to find matching ends.

- **Discrete Tokens (`|`, `$$`):** Have no closing pairs. They are registered instantly at their string index, but are subject to the same Interval Culling rules to ensure they only act at the top level of the current scope.

-----

### Polymorphic AST Generation & The Grandchild Trap

**Trap Avoided:** _Leaving raw `Token` objects for the Evaluator to process procedurally, AND creating unnecessary dummy wrapper nodes._

To keep the Evaluator lean, the Parser converts every execution token into a strongly typed subclass of a base `ASTNode`. However, to avoid the "Grandchild Trap" (wrapping every expanded macro in a dummy `ScopeNode` just to manage scope), the Parser does not return a single root node. Instead, it returns a flat `Tuple[List[Definition], List[ASTNode]]`.

- `TEXT` tokens become `TextNode`s.
- `INVOCATION` tokens become Invocation Nodes of some type.
- `SCOPE` tokens become `ScopeNode`s.

### Scope Hoisting (The Footnote Architecture)

**Trap Avoided:** _Mutating global context during the parsing phase._

Parsing is deterministic; evaluation is path-dependent (randomized). If the Parser pushed definitions to the global context while building the tree, discarded PRNG branches would leak state.

- **The Solution:** The Parser cleanly separates State from Data. It identifies all `DEFINITION` tokens at the zero-depth level, converts them into standard Data Objects (not AST nodes), and returns them in the `local_definitions` list of its output Tuple.
- This allows users to write massive blocks of variable definitions at the very bottom of their text (like footnotes). The `_evaluate_scope()` method pushes these to the Context Stack exactly when the node evaluates, without prematurely mutating state.

**State Cleanup Guarantee:** When `_evaluate_scope()` pushes to the Context Stack, it tracks the integer count of its pushes. It uses a `try...finally` block to execute exact `popleft()` and `pop()` counts when exiting the scope, completely resolving the "Pop Paradox" and ensuring zero state leakage.

-----

## 4\. Phase C: State Management (The Context Stack)

The Context Stack is the memory engine. It is strictly a Search Engine and Data Store; it never executes AST logic.

### The LIFO Deque & Priority Queue

Definitions are scoped contextually. The stack uses a Double-Ended Queue (Deque):

- **Strong Definitions (`:`):** Pushed to the HEAD (Left). Act as local overrides.

- **Weak Definitions (`::`):** Pushed to the TAIL (Right). Act as global defaults.

### The 3D Orthogonal Syntax Matrix

The engine completely decouples the definition syntax into three independent dimensions: **Class**, **Position**, and **Strength**. This allows fully combinatorial, modular definition logic.

1. **Class (When does this apply? - Start Marker):**
   - `:` -> Bounded Macro (Explicit invocation keys)
   - `:<` -> Unbounded Pre-Pattern (Applied before parsing)
   - `:>` -> Unbounded Post-Pattern (Applied after evaluation)
2. **Position (Where does the value go? - Concat Vector):**
   - _[Empty]_ -> Base Terminator (Overwrites/Sets the root value)
   - `<` -> Left-Concat (Prepends to the base/match)
   - `>` -> Right-Concat (Appends to the base/match)
3. **Strength (Stack Priority - Override Level):**
   - `:` -> Strong (Pushed to HEAD, evaluated first, acts as local override)
   - `::` -> Weak (Pushed to TAIL, evaluated last, acts as global fallback)

_Example Combinations:_

- `:key:value` (Bounded, Base, Strong)
- `:<pattern<::prefix` (Pre-Pattern, Left-Concat, Weak)
- `:>pattern>:suffix` (Post-Pattern, Right-Concat, Strong)

### The Search-Terminating Dual-Accumulator

**Trap Avoided:** _Using recursive definitions (`:key: <key> | val`) to build arrays._ Recursion forces the engine to eagerly collapse PRNG pools, destroying flat peer-to-peer data structures.

- **The Solution:** Array building happens silently in the Context Stack search phase.

- When a key is requested, the stack searches **Left-to-Right (Head-to-Tail / Strongest-to-Weakest)**.

- It accumulates any Left-Concat (`<:`) or Right-Concat (`>:`) definitions it finds into a running list.

- The exact moment it hits a Base definition (`:` or `::`), the search **terminates**, yielding the final ordered list. This natively resolves shadowing while allowing infinite, scoped list extensions.

### The Regex Identity Trap

**Trap Avoided:** _Allowing Unbounded Patterns (`:<`) to accumulate each other._

Unlike Bounded Macros (which have explicit string keys), Unbounded Patterns are mathematical search rules. Attempting to concatenate regex replacements in the stack causes severe capture-group paradoxes.

- **The Solution:** Context Stack accumulation strictly applies to Bounded Macros. For Unbounded Patterns, using a concat action (`<:` or `>:`) acts as an automated compiler shorthand that implicitly injects the regex `\g<0>` capture token to preserve the matched text, sparing the user from manual escape sequence hell.

### The Multi-Line Value Wrapper (`<< >>`)

- To support 'Container Macros' and multi-line values without breaking the zero-depth interval tracking, the engine uses explicit Value Wrappers. If `<<` immediately follows a definition's strength marker, the Lexer overrides the End-of-Line termination rule. It initiates a pushdown automaton to track nested `<<` and `>>` pairs, ensuring that nested blocks (like definitions inside definitions) are safely captured as a single, inert literal string. The engine uses **Strict Literal Capture**; leading and trailing newlines inside the block are kept, granting the user explicit control over text flow.

-----

## 5\. Phase D: Expansion & Execution (Recursive Walks)

### Path-Hashed PRNG Determinism

To guarantee that a specific randomized prompt yields the exact same output every time a specific seed is used---even if the prompt is heavily branched---the random state cannot rely on a global counter.

- Every Child of a Node uses a uniquely suffixed Parent Seed based on the index of that Key String (or none, for ScopeNodes).
- This perfectly isolates sibling tree branches. Modifying one part of a prompt will not butterfly-effect the random rolls of an unrelated branch.

### The Bounded Token Lifecycle (Option Selection)

The internal processing logic for different nodes are heavily overlapping, allowing significant code reuse. When evaluated, they execute this exact sequence:

**Trap Avoided:** _Splitting strings before Lexing._ Using Python's `.split('|')` would shatter nested syntax like `<Macro | param:val>`. The Lexer must identify the safe boundaries first.

**Trap Avoided:** _Eager Payload Flattening._ We initially considered eagerly resolving payloads to apply modifiers, but this broke nested hierarchical weights (`A | {B|C}`). Modifiers must be attached to the Invocation key directly (`<2$$key>`) so the engine only splits the top-level buckets, preserving the nested lazy hierarchy.

### The Inside-Out Concatenation Architecture

**Trap Avoided:** _Context Stack managing string buffers or sorting logic._

When the Context Stack returns the list of concatenated definitions (from the Dual-Accumulator search), it returns them in the exact order they were searched (Strongest to Weakest, ending in the Base).

- The Context Stack does **not** need to sort this list or manage left/right string buffers.

- Because the strongest modifiers are processed first, they are concatenated directly against the Base string. Weaker modifiers are processed later, appending to the outer edges. This naturally builds the string from the **Inside-Out**, perfectly guaranteeing that Local Scope wraps tighter than Global Scope without any complex tracking overhead.

### The Anonymous Escape Block

TODO this should be a dedicated node type for the Parser to output

**Trap Avoided:** _Global Lexer rules for escape sequences (The Slash Collision Trap)._ Applying `/ /` escape logic to all text destroys standard file paths and URLs.

- **The Solution:** `/ /` delimiters are restricted entirely to Definition values (to explicitly separate regex from literal invocations).

- To inject an inline escape sequence (like a newline), the engine checks if the Invocation's (by the Parser as a Token?) Payload string (TODO after applying its Parent's Local Pre-Patterns, I think?) starts and ends with `/` (e.g., `</\n/>`).

- If true, it bypasses the Context Stack entirely, strips the slashes, decodes the Unicode escape natively, and returns the literal characters. This allows escapes to be dynamically generated by macros while remaining perfectly sandboxed from standard text.

To prevent the Slash Collision Trap, the engine treats standard escape sequences (like `\n`, `\t` in `C:\new_folder`) as generic text. Escape characters are parsed and stripped if they immediately precede a custom engine syntax marker (e.g., `\:` or `\<`). Standard escapes only execute natively inside the Escape Block `</.../>` sandbox or within explicitly delimited `/ /` regex patterns in Definitions.

## 6\. Additional Technical Definitions & Paradigms

This is the distilled, expert-level encapsulation of the engine's fundamental principles, derived directly from the architectural decisions made during our system design.

### 1: Lexical Analysis Paradigms

- **Interval-Tracking Speculative Lexer:** A zero-copy lexical scanner that records token boundaries as integer start/end pairs rather than buffering string slices, ensuring $O(N)$ linear time complexity.
- **Zero-Depth Interval Culling:** The resolution algorithm that discards any registered token boundaries that fall strictly within the bounds of a higher-order hierarchy marker, safely neutralizing unbalanced brackets and natively protecting nested syntax.
- **Boundary vs. Discrete Tokenization:** The distinction between paired contextual markers (eg `< >`, `{ }`) which require pushdown-automata tracking, and zero-depth singular markers (`|`, `$$`) which are registered instantly.

### 2: Parsing & Structural Paradigms

- **The Grandchild Trap & Base Template Pattern:** The architectural realization that returning parsed sub-trees wrapped in dummy "Block Nodes" creates unnecessary memory bloat and deepens the call stack.
- **Breadth-Eager / Depth-Lazy Parsing:** The engine eagerly builds a polymorphic AST for the current zero-depth scope, but strictly treats all nested macro/group contents as inert raw strings until explicitly invoked.
- **Polymorphic AST Generation:** The parser functions as a Factory, mapping lexed tokens to strongly typed objects (eg TextNode, ScopeNode, Invocation Nodes) that encapsulate their own processing logic to prevent primitive-obsession in global Evaluation logic.
- **Scope Hoisting (Footnote Architecture):** The structural decoupling of State (Definitions) from Data (Outputs) during Parsing, allowing Definitions to be position-independent within their Scope (outside of overriding an earlier Definition).

### 3: Evaluation Paradigms

- **Lazy-Evaluation Recursion:** The fundamental guarantee that the Lexer and Parser are invoked as needed (just-in-time compilation), ensuring discarded PRNG branches consume zero parsing cycles.
- **Path-Based PRNG Determinism:** The state-tracking mechanism where a child node's random seed is deterministically computed by its relative position within its Parent, isolating tree branches from sibling's insertions/deletions.
- **Inside-Out Scoped Concatenation:** The principle that nested tree modifiers apply strictly from the innermost scope outward, inherently prioritizing local scope tightly against the base string before applying global scope.
- **Escape Resolution:** The "Anonymous Escape Block" acts before Invocation Payload Evaluation and dictionary-lookup Resolution Logic take place. TODO confirm this behavior or when this check should happen and bypass remaining normal Invocation processing

### 4: Context & State Management Paradigms

- **LIFO Dual-Accumulator Context Deque:** The state engine architecture where definitions are pushed Strong-to-Head and Weak-to-Tail.
- **Search-Terminating Accumulator Search:** The Context Stack lookup algorithm that traverses the deque Head-to-Tail (Strongest-to-Weakest), accumulating Left/Right directional definitions until it strikes a Base and terminates, cleanly resolving shadowing and array extension.
- **3D Orthogonal Syntax Matrix:** The complete dimensional decoupling of a definition's **Class** (Bounded `:`, Unbounded Pre `:<`, Unbounded Post `:>`), **Position** (Base _empty_, Left `<`, Right `>`), and **Strength** (Strong `:`, Weak `::`), allowing infinitely scalable, combinatorial definition logic without hardcoding specific syntax groupings.
- **Regex Identity Trap Avoidance:** The rule that Bounded Macros accumulate Values from matching Definitions, while Unbounded Pre/Post Patterns are treated as discrete, non-accumulating sequential passes to prevent capture-group paradoxes.
- **Shorthand Pattern Injection:** The automated AST behavior where applying directional accumulation (`<:`, `>:`) to an Unbounded Pattern implicitly injects the regex `\g<0>` token, shielding the user from backreference syntax while maintaining flat, individual application.
