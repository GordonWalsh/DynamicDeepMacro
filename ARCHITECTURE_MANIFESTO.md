# The Core Architecture Manifesto: Macro Engine System Design

This document serves as the comprehensive, expert-level technical foundation for the Macro Engine. It details the system's structure, processing pipelines, and the strict architectural principles governing its operation. It explicitly documents not only the final design decisions but the specific compiler traps and logical paradoxes that necessitated them.

---

## 1\. System Overview & The Eager/Lazy Paradigm

The Macro Engine is a deterministic, context-aware, text-replacement compiler designed to handle highly nested, randomized structural logic. The Macro Engine operates on a phased Evaluation Pipeline, roughly divided into: Pre-Processing (i.e. `LexAndSegment`)

### The Two-Pass Scope Lifecycle

**TODO timing of `PositionalNode`** - I think doing some sort of prepass before the `UnscopedInvocationNode`s in the Expansion Pass. If all `PositionalNode`s are processed before starting on `UnscopedInvocationNode`s, then the Definitions needed for the Positional Invocations can be safely overwritten inside of a `UnscopedInvocationNode`
To satisfy the "Footnote Architecture" (order-independent definitions), the engine utilizes a dual-pass approach over the AST:

1. **Expansion Pass:** A recursive tree-walk targeting `UnscopedInvocationNode`s. It queries the Context Stack, resolves dictionary lookups, and hoists Definitions to a staging pool to prevent cross-contamination between Sibling Invocations.
2. **Execution Pass:** A recursive tree-walk targeting `TextNode`s, `ScopeNode`s, and `ScopedInvocationNode`s. It pushes a Scope Sentinel, executes the Child Node (yielding literal strings), applies Context Pre/Post-Patterns, concatenates the result, and pops the sentinel.

The foundational paradigm of the entire engine is **Breadth-Eager, Depth-Lazy Execution** (Just-In-Time Compilation), executed across a Unified AST using Symmetrical Passes:

- **Expansion:** A recursive tree-walk targeting `UnscopedInvocationNode`s to resolve them into Definitions and flat Nodes.
- **Execution:** A recursive tree-walk targeting `TextNode`s, `ScopeNode`s, and `ScopedInvocationNode`s to concatenate them into Literal Strings.
- **Breadth-Eager:** At any given step, the engine fully Lexes and Parses the flat, zero-depth layer of the current text Payload into polymorphic objects.
- **Depth-Lazy:** The engine never Parses or Evaluates the internal contents of a macro or multi-Segment Group until that specific branch is Selected by the PRNG (Pseudo-Random Number Generator). Losing branches are discarded early, saving CPU cycles.
- _Note: This is a general principal common to most operations, not a hard rule that must be blindly followed._

### Functional Composition & AST Avoidance

The engine prevents AST depth-bloat through Functional Composition rather than literal object wrapping. Explicit `ScopedInvocationNode` and `UnscopedInvocationNode` objects are processed during Execution and Expansion respectively. A Scoped Invocation `<A|B>` is not direct syntactic sugar for a ScopeNode around an Unscoped Invocation object, though it can generally be understood to behave that way. Node objects capture a need for further (maybe recursive) processing, not strictly for Literal Text outputs.
Similarly, Positional Digits (`<0>`) avoid injecting massive overhead into the main Definition dictionary by mapping to a dedicated, ephemeral array on the Context. The Parser outputs a `PositionalNode`, which looks up Definitions from this array rather than sweeping the Context stack, but otherwise acts similarly to a standard `InvocationNode` logic.

### Eager Evaluation Serialization (The Escape Block Strategy)

"Eager" Definitions (`::Key:Value`) and Arguments freeze a dynamic string by executing it immediately at the time of Parsing, utilizing the exact state of the Inherited Context at that point. To prevent the generated Literal Text from undergoing double-evaluation when the Definition is eventually retrieved, the engine serializes the frozen text using the existing explicit Escape Block syntax (`</.../>`).

1. **Evaluation & Escaping:** The engine evaluates the payload, then runs a substitution on the resulting Literal Text to replace any literal `<` and `>` characters with their hexadecimal equivalents (`\x3c` and `\x3e`).
2. **Serialization:** The string is wrapped in `</` and `/>` and stored as the Definition's Raw Value.
3. **Retrieval Compatibility:** Because the Eager result is serialized as standard syntax, it behaves perfectly alongside Lazy text. If an Option is appended later (`::Key:{A|B}`, `:Key>:|C`), the dictionary cleanly resolves the combined Value-Pattern as `</A/>|C`. When Expanded, the Lexer processes the Escape Block, native Python `codecs.decode` unpacks the hex characters, and the output remains safely Literal.

### Regex Pattern Matching as a Substitution Layer

Regex Definitions (`:/pattern/:/replacement/`) do not bypass the standard Macro Engine processing pipeline. They are not a parallel evaluation system; they are strictly a matching and substitution layer operating _within_ the Dictionary Lookup phase.

When `DefLibrary.resolve()` encounters a Regex Value-Pattern in a Definition, it executes a standard `re.sub()` operation from the Regex Key-Pattern or `re.escape()`d plaintext Key (acting as a dynamic, pattern-based equivalent of a simple 'key' -> 'value' string replacement). The string produced by this substitution is treated strictly as **Raw Text**.

- **Dynamic Syntax Construction:** Because Regex outputs Raw Text, it can be used to dynamically generate engine syntax. For example, a definition like `:/wild_(\w+)/:/<pet_\1>/` successfully constructs a new Invocation (`<pet_dog>`), which then flows directly into the standard Phase 2 Expansion Pass to be expanded and executed identically to static input text.

---

## 2\. Phase A: Lexical Analysis (The Lexer)

The Lexer converts raw strings into a flat list of `Token` objects. It is completely blind to execution logic, randomness, and context.

### Interval-Tracking Speculative Lexer

The Lexer operates in $O(N)$ linear time by avoiding Python string buffering (which is catastrophically slow due to immutability). Instead, it runs a single pass over the input string, tracking the integer indices of start and end markers using independent pushdown automata (stacks) for each syntax type. String slicing happens exactly once at the end of the pass.

### Zero-Depth Interval Culling

To solve the paradox of malformed brackets (e.g., `< { > }`), the Lexer employs an interval culling algorithm.

- **The Rule:** If a token boundary set (like a `{ }` group or a `|` split) falls strictly within the registered bounds of a higher-order boundary (like a `< >` invocation), the inner marker is consumed and neutralized.

- **The Result:** The Lexer only outputs top-level (zero-depth) tokens. Inner brackets remain inert literal text. This perfectly protects nested syntax and isolates user typos from destroying the entire document structure.

### Boundary vs. Discrete Tokenization

- **Boundary Tokens (`< >`, `{ }`):** Require push/pop stacks to find matching ends.

- **Discrete Tokens (`|`, `$$`):** Have no closing pairs. They are registered instantly at their string index, but are subject to the same Interval Culling rules to ensure they only act at the top level of the current scope.

---

### Polymorphic AST Generation & The Grandchild Trap

**Trap Avoided:** Leaving raw `Token` objects for the Evaluator to process procedurally, AND creating unnecessary dummy wrapper nodes.\_

To keep the Evaluator lean, the Parser converts every execution token into a strongly typed subclass of a base `ASTNode`. However, to avoid the "Grandchild Trap" (wrapping every expanded macro in a dummy `ScopeNode` just to manage scope), the Parser does not return a single root node. Instead, it returns a flat `Tuple[List[Definition], List[ASTNode]]`.

- `TEXT` tokens become `TextNode`s.
- `INVOCATION` tokens become Invocation Nodes of some type.
- `SCOPE` tokens become `ScopeNode`s.

### Scope Hoisting (The Footnote Architecture)

**Trap Avoided:** _Mutating global context during the parsing phase._

Parsing is deterministic; evaluation is path-dependent (randomized). If the Parser pushed definitions to the global context while building the tree, discarded PRNG branches would leak state.

- **The Solution:** The Parser cleanly separates State from Data. It identifies all `DEFINITION` tokens at the zero-depth level, converts them into standard Data Objects (not AST nodes), and returns them in its output Tuple.

**State Cleanup Guarantee:** When the engine pushes Definitions to the Context Stack, it tracks the integer count of its pushes or uses sentinel objects to mark Scope Transitions. When exiting a Scope, all Definitions that were added by that Child are removed, ensuring zero state leakage.

---

## 4\. Phase C: State Management (The Context Stack)

The Context Stack is the engine memory. It is strictly a Data Store; it never executes AST logic.

### The LIFO Deque & Priority Queue

Definitions are scoped contextually. The stack uses a Double-Ended Queue (Deque):

- **Strong Definitions (`:`):** Pushed to the HEAD (Left). Act as local overrides.

- **Weak Definitions (`::`):** Pushed to the TAIL (Right). Act as global defaults.

### - Orthogonal Definition Syntax Matrix

The parseing logic for Definition syntax follows the pattern: `[Timing][Class]KeyPattern[Position][Strength] Value`. This fully decouples Evaluation Timing, Class, Position, and Strength, allows fully combinatorial, modular definition logic from simple building blocks. Some combinations may have limited practical applications, but still function correctly according to each individual axis' mandate.

1. **Timing (When should the Value be Evaluated, Definition or Invocation?):**
    - `:` -> Lazy Evaluation (Raw Text stored, Evaluated after Resolution)
    - `::` -> Eager Evaluation (Evaluated at Definition, Literal Text stored)
2. **Class (When does this apply?):**
    - _Empty_ -> Bounded Macro (Explicit invocation keys)
    - `<` -> Unbounded Pre-Pattern (Applied before parsing)
    - `>` -> Unbounded Post-Pattern (Applied after evaluation)
3. **Position (Where does the value go? - Concat Vector):**
    - _Empty_ -> Base Terminator (Overwrites/Sets the root value)
    - `<` -> Left-Concat (Prepends to the base/match)
    - `>` -> Right-Concat (Appends to the base/match)
4. **Strength (Stack Priority - Override Level):**
    - `:` -> Strong (Pushed to HEAD, evaluated first, acts as local override)
    - `::` -> Weak (Pushed to TAIL, evaluated last, acts as global fallback)

_Example Combinations:_

- `::key:value` (Eager, Bounded, Base, Strong)
- `:<pattern<::prefix` (Lazy, Pre-Pattern, Left-Concat, Weak)
- `:>pattern>:suffix` (Lazy, Post-Pattern, Right-Concat, Strong)

### The Search-Terminating Dual-Accumulator

**Trap Avoided:** _Using recursive definitions (`:key: <key> | val`) to build arrays._ Recursion forces the engine to eagerly collapse PRNG pools, destroying flat peer-to-peer data structures.

- **The Solution:** Array building happens silently in the Context Stack search phase.

- When a key is requested, the stack searches **Left-to-Right (Head-to-Tail / Strongest-to-Weakest)**.

- It accumulates any Left-Concat (`<:`/`<::`) or Right-Concat (`>:`/`>::`) definitions it finds into a running list.

- The exact moment it hits a Base definition (`:` or `::`), the search **terminates**, yielding the final ordered list. This natively resolves shadowing while allowing infinite, scoped list extensions.

### The Regex Identity Trap

**Trap Avoided:** _Allowing Unbounded Patterns (`:<`/`:>`) to concatenate each other._

Unlike Bounded Macros (which have a single explicit Key-String per Invocation), Unbounded Patterns are mathematical search rules. Attempting to concatenate regex replacements in the stack causes severe capture-group paradoxes.

- **The Solution:** Context Stack accumulation strictly applies to Bounded Macros. For Unbounded Patterns, using a concat action (`<:` or `>:`) acts as an automated compiler shorthand that implicitly injects the regex `\g<0>` capture token to preserve the matched text, preserving the meaning of the concat Definitions while maintaining the efficient sequential application of Unbounded Definitions.

### The Multi-Line Value Wrapper (`<< >>`)

- To support 'Container Macros' and multi-line values without breaking the zero-depth interval tracking, the engine uses explicit Value Wrappers. If `<<` immediately follows a Definition's strength marker, the Lexer overrides the End-of-Line termination rule for Definitions. It initiates a pushdown automaton to track nested `<<` and `>>` pairs, ensuring that nested blocks (like definitions inside definitions) are safely captured as a single, inert literal string. The engine uses **Strict Newline Capture**; leading and trailing newlines inside the block are kept, granting the user explicit control over text flow at both end's transitions.

---

## 5\. Phase D: Expansion & Execution (Recursive Walks)

### Path-Hashed PRNG Determinism

To guarantee that a specific randomized prompt yields the exact same output every time a specific seed is used---even if the prompt is heavily branched---the random state cannot rely on a global counter.

- Every Child of a Node uses a uniquely suffixed Parent Seed based on the index of that Key String (or none, for ScopeNodes).
- This perfectly isolates sibling tree branches. Modifying one part of a prompt will not butterfly-effect the random rolls of an unrelated branch.

### The Bounded Token Lifecycle (Option Selection)

The internal processing logic for different nodes are heavily overlapping, allowing significant code reuse.

**Trap Avoided:** _Splitting strings before Lexing._ Using Python's `.split('|')` would shatter nested syntax like `<Macro | param:val>`. The Lexer must identify the safe boundaries first.

**Trap Avoided:** _Eager Payload Flattening._ We initially considered eagerly resolving payloads to apply modifiers, but this broke nested hierarchical weights (`A | {B|C}`). Modifiers must be attached to the Invocation key directly (`<2$$key>`) so the engine only splits the top-level buckets, preserving the nested lazy hierarchy.

### The Inside-Out Concatenation Architecture

**Trap Avoided:** _Context Stack managing string buffers or sorting logic._

When the Context Stack returns the list of concatenated definitions (from the Dual-Accumulator search), it returns them in the exact order they were searched (inherently Strongest to Weakest, ending in the Base).

- The Context Stack does **not** need to sort this list or manage left/right string buffers.

- Because the strongest modifiers are processed first, they are concatenated directly against the Base string. Weaker modifiers are processed later, appending to the outer edges. This naturally builds the string from the **Inside-Out**, perfectly guaranteeing that Local Scope wraps tighter than Global Scope without any complex tracking overhead.

### The Anonymous Escape Block

TODO this should be a dedicated node type for the Parser to output

**Trap Avoided:** _Global Lexer rules for escape sequences (The Slash Collision Trap)._ Applying `/ /` escape logic to all text destroys standard file paths and URLs.

- **The Solution:** `/ /` Regex boundaries are restricted entirely to Definition values (to explicitly designate interpreting as Regex instead of as engine syntax).

- To inject an inline escape sequence (like a newline), the engine checks if the Invocation's (by the Parser on a Token?) Payload string (TODO after applying its Parent's Local Pre-Patterns, I think?) starts and ends with `/` (e.g., `</\n/>`).

- If true, it bypasses the Context Stack entirely, strips the slashes, decodes the Unicode escapes natively, and returns the Literal characters. This allows escapes to be dynamically generated by macros while remaining perfectly sandboxed from standard text.

To prevent the Slash Collision Trap, the engine treats standard escape sequences (like `\n`, `\t` in `C:\new_folder`) as generic text. Escape characters are parsed and stripped if they immediately precede a custom engine syntax marker (e.g., `\:` or `\<`). Standard escape sequences only execute natively inside the Escape Block `</.../>` sandbox or within explicitly delimited `/ /` regex patterns in Definitions.

## 6\. Additional Technical Definitions & Paradigms

### 1: Lexical Analysis Paradigms

- **Interval-Tracking Speculative Lexer:** A zero-copy lexical scanner that records token boundaries as integer start/end pairs rather than buffering string slices, ensuring $O(N)$ linear time complexity.
- **Zero-Depth Interval Culling:** The resolution algorithm that discards any registered token boundaries that fall strictly within the bounds of a higher-order hierarchy marker, safely neutralizing unbalanced brackets and natively protecting nested syntax.
- **Boundary vs. Discrete Tokenization:** The distinction between paired contextual markers (eg `< >`, `{ }`) which require pushdown-automata tracking, and zero-depth singular markers (`|`, `$$`) which are registered instantly.

### 2: Parsing & Structural Paradigms

- **The Grandchild Trap & Base Template Pattern:** The architectural realization that returning parsed sub-trees wrapped in dummy "Block Nodes" creates unnecessary memory bloat and deepens the call stack.
- **Breadth-Eager / Depth-Lazy Parsing:** The engine eagerly builds a polymorphic AST for the current zero-depth scope, but strictly treats all nested macro/group contents as inert raw strings until explicitly invoked.
- **Polymorphic AST Generation:** The parser functions as a Factory, mapping lexed tokens to strongly typed objects (eg TextNode, ScopeNode, Invocation Nodes) that encapsulate their own processing logic to prevent primitive-obsession in global Evaluation logic.
- **Scope Hoisting (Footnote Architecture):** The structural decoupling of State (Definitions) from Data (Outputs) during Parsing, allowing Definitions to be position-independent within their Scope (outside of overriding an earlier Definition).

### 3: Evaluation Logic & Option Selection Timing

Option Selection is handled dynamically based on the object type rather than in a unified compiler stage:

- **ScopeNodes (Raw Text):** Perform Option Selection immediately after Lexing to cull unselected branches before Parsing.
- **InvocationNodes (Dictionary Queries):** Do not cull Segments natively. They Lex, Resolve all Segments against the dictionary, and then apply Modifiers to the Resolved Values individually to Select Options.
- **Ephemeral Instantiation:** Child AST branches generated during macro expansion or Group selection are instantiated dynamically, Evaluated, and immediately garbage-collected.
- **Lazy-Evaluation Recursion:** The fundamental guarantee that the Lexer and Parser are invoked as needed (just-in-time compilation), ensuring discarded PRNG branches consume zero parsing cycles.
- **Path-Based PRNG Determinism:** The state-tracking mechanism where a child node's random seed is deterministically computed by its relative position within its Parent, isolating tree branches from sibling's insertions/deletions.
- **Inside-Out Scoped Concatenation:** The principle that nested tree modifiers apply strictly from the innermost scope outward, inherently prioritizing local scope tightly against the base string before applying global scope.
- **Escape Resolution:** The "Anonymous Escape Block" acts before Invocation Payload Evaluation and dictionary-lookup Resolution Logic take place. TODO confirm this behavior or when this check should happen and bypass remaining normal Invocation processing

### 4: Context & State Management Paradigms

- **LIFO Dual-Accumulator Context Deque:** The state engine architecture where definitions are pushed Strong-to-Head and Weak-to-Tail.
- **Search-Terminating Accumulator Search:** The Context Stack lookup algorithm that traverses the deque Head-to-Tail (Strongest-to-Weakest), accumulating Left/Right directional definitions until it strikes a Base and terminates, cleanly resolving shadowing and array extension.
- **Orthogonal Syntax Matrix:** The complete dimensional decoupling of a definition's Evaluation **Timing** (Lazy `:`, Eager `::`), **Class** (Bounded _empty_, Unbounded Pre `<`, Unbounded Post `>`), **Position** (Base _empty_, Left `<`, Right `>`), and **Strength** (Strong `:`, Weak `::`), allowing infinitely scalable, combinatorial definition logic without hardcoding specific syntax groupings.
- **Regex Identity Trap Avoidance:** The rule that Bounded Macros accumulate Values from matching Definitions, while Unbounded Pre/Post Patterns are treated as discrete, non-accumulating sequential passes to prevent capture-group paradoxes.
- **Shorthand Pattern Injection:** The automated AST behavior where applying directional accumulation (`<:`, `<::`, `>:`, `>::`) to an Unbounded Pattern implicitly injects the regex `\g<0>` token, shielding the user from backreference syntax while maintaining flat, individual application.
- **The "Proximity of Intent" Priority Hierarchy:** Because the engine processes different Node classes in distinct phases (e.g., Expansion vs. Execution, Lazy passes vs. Eager passes), it inherently groups Definitions into functional classes. Rather than attempting complex Lexical Index Sorting to map Definitions back to their exact physical character offsets, the engine embraces a strict "Class Priority" hierarchy. Definitions explicitly written to modify a specific target overpower Definitions written loosely nearby. The resolution hierarchy (from outermost in Library to innermost) is mathematically guaranteed as follows:
    1. Invocation Co-Segments (e.g., `<Macro|:Key:Value>`)
    2. Top-Level Eager Definitions (`::`)
    3. Top-Level Lazy Definitions (`:`)
    4. Definitions resulting from Positional Invocation Expansion
    5. Unscoped Hoisted Definitions (Sibling Context)
    6. Inherited Context (Parent Context)
- **Functional State Composition:** To enforce the Proximity of Intent hierarchy without relying on sorting algorithms or multi-dimensional physical indexing, the engine utilizes chronological layer composition. During a Node's processing lifecycle, different classes of definitions are collected into isolated staging libraries. By selectively merging these staging libraries together from weakest to strongest (creating "outer" and "inner" layers) _before_ pushing them to the main Context Stack, the engine maintains a purely O(1) appending logic while perfectly preserving the intended lexical hierarchy.

## 7\. Processing Pipeline

_TODO: Currently covered mainly from the perspective of Invocation-type Nodes, to be expanded upon._
This is an overview of the various steps that different Nodes may use to process their contents to return the right type of result for their Node type, or when a piece of Raw Text needs to be Evaluated. A particular Node type may only need to carry out a subset of these steps. This overview attempts to provide a complete list of steps so the reader understands the required order of operations and information flow of the engine, but the actual implementation should have major phases and steps grouped into common functions and internal class logic.

### Phase 0: Pre-Processing

1. If applicable, read the outermost Scope layer (the Parent's Local Definitions) of Context.DefLibrary to get Pre-Patterns and apply them to the Raw Text.
2. If applicable, push a Scope Sentinel boundary onto Context.DefLibrary to separate Inherited Definitions from new Local ones.
3. Lex the internal Payload (or engine input string) into a single long List of Tokens of varying flavors.
   TODO: How does the Lexing function interact with Arguments in Invocation Payloads? Are they a full-on Token Type, or do they get folded into the `DEFINITION` type? Does the Lexer need a flag to tell it whether to detect Arguments? Is there a realistic meaning to non-Definition Argument syntax outside of an Invocation Segment (eg, is it effectively a comment)?

### Phase 1A: Selection (Non-Invocations and general Raw Text)

_Invocation-type Nodes would (currently, might be a future feature to add) skip this step and perform the full Resolution Phase instead, but for general Raw Text (eg engine root input) or non-Invocation Node (eg `ScopeNode`) Payloads, this step is performed._
TODO: Are Separators Interleaved as Tokens or are they Expanded and the Nodes interleaved with Definitions combining somehow? I think the former, for consistency, but may have weird effects?

1. Extract and Parse the Modifier Token from the front of the Token List, or instantiate a default Modifier.
2. Lex (and Expand if needed? _later note: maybe leave it as Tokens?_) the Separator text from the Modifier.
    - If this requires PRNG Selection itself or produces Definition objects, we just accept that for now. Details TBD?
3. Split the Token List (sans Modifier) into Sublists at the Top-Level `SPLIT` Tokens. Use the Modifier properties and PRNG Seed to pick Segments as needed. TODO exact mathematical/combinatorial logic but let's say we get a list of Segment indices.
4. Interleave the Token Sublists for the Step 3 indices with the Separator Token List from Step 2 to produce one flat List of Tokens combining all Selected Options and Modifier Separators.

### Phase 1B: The Resolution Phase (Invocations Only)

_This section only applies to `ScopedInvocationNode` and `UnscopedInvocationNode`. It is the process of turning a segmented Payload into raw, unparsed Resolved Text._
_TODO: I think an Escape Block syntax might get branched this way during processing as well, and if so should have a detection and reroute to that behavior._

1. Separate the token List at Top-Level `SPLIT` Tokens to get a List of Sublists, each representing one Segment with Modifier still attached.
2. Sort into Raw Keys (not starting with `:`) for now vs Definitions and Positional Arguments (starting with `:`) for later.
    - TODO: How does this all gets coordinated between the Lexer, Parser, and this sorting operation (see Pre-Processing `TODO` above)? The Payload should already be Lexed to Tokens before entering Resolution (I think?) unless we actually need to branch the pipeline before that (eg doing first/last character checks on Invocation Payloads, but that should have been handled by the Parser creating the Node object we're currently inside of). Trying to do some weird first-Token-type switch but also check the first character of the Token text (Payload?) seems like the wrong setup.
    - TODO: is it valid to have Modifiers on Definition and especially Argument Segments, and where do they go relative to other syntax? Normally Modifiers are not supposed to go with the Value-Pattern (on the Invocation instead), but should that change in this situation? I don't think we would want to deal with Modifiers in an other-wise single-digit Positional Invocation, for example?
3. **Key-String Evaluation:** Trigger overarching String Evaluation specifically on the Raw Key segments to resolve dynamic keys (e.g., `<Weapon_<Element>>` -> `Weapon_Fire`).
    - TODO: I'm not sure if it would be be better to Evaluate all Key-Strings first and then create `Resolution`s, or if it should loop over the Key-String Segments and do Evaluation and `Resolution` immediately.
4. **Resolution:** Instantiate `Resolution` worker objects for each Evaluated Key-String + its attached Modifier.
    - The `Resolution` object traverses the Context Deque, accumulates matching Definition Payloads, and obtains a single combined **Resolved Value** (Raw Text).
    - It then Lexes that and applies the Modifier from the Parent Invocation (or default single random Option) to PRNG Option Selection (as described above), and returns single flat Token List.
        - TODO: It may be better to split this off, so each Key-String Segment (Key Segment?) of the Parent Invocation has three steps: Evaluate Raw Key, do Resolution, do Selection. I think this also cleans up how Positional Invocations slip in, skipping that Evaluation and shortcutting Resolution but still having Selection.
5. **Consolidation:** Join the Token Lists from each Key Segments into a single flat List. Since the Selection was already performed on each Segment individually, there shouldn't be any Top-Level Splits left to worry about (unless deliberately reintroduced by custom Modifer Separator, but TODO we'll examine that edge case behavior later).
6. **Definition Loading:** Take the inert Positional Arguments and Definition Values identified in Step 1 and load them into the current Context's flat Positional Array so they are ready for Phase II.
    - TODO: I think it might make sense for the Definitions in the Parent Invocation Segments to actually count _after_ the (ie, stronger than) the Definitions in the Resolved Values. That way, you have the behavior of Invoking a Macro but overriding a Definition it contains, which I think more closely matches user intent and expectations. I'm not sure how this plays out with the nested Recursive Expansion though, might need to work through some examples.

_In processing `PositionalNode`s, there are no Key-Strings or other Segments to worry about, they will only match the single Definition for their index, and they do not load Positional Definitions for Children. Since almost all of the complex behavior handled by the `Resolution` object is not necessary, they can just directly access their Positional Definition from the Context array and use its Value-Pattern as the Resolved Value, then apply Selection if needed._

### Phase 2: The Common Expansion Pass

_This is a standardized AST tree-walk and where Invocation-type Nodes and non-Invocation Nodes should merge back together. It starts with a flat Token List from a Phase 1 operation, whether a 1A Selection or a 1B Resolution, but it is exactly the same pass performed on both regardless of origin. A Resolution process may have altered the Context object or populated some initially-empty containers, but the Expansion should be able to handle either case without needing separate functions or anything._

1. **Parsing:** Parse the Token List into a list of Child AST Nodes and Top-Level Definitions. TODO: Should the Definitions actually be parsed to Objects (would this need strength-tracking or two lists then) or left as Tokens with Strength implicit in the text?
   _TODO: I'm not sure if Top-Level Definitions (Step 1) should be applied to Positionals, since they are retrieving content from "above" that (the Parent Invocation's Segments), but then there's maybe inconsistency with by-index vs by-name Invocations of Parent Definition Segments?_
2. **Positional Early-Capture (`PositionalNode` handling):** - Scan the top-level Child list for `PositionalNode`s (e.g., `<1>`). - Query the Positional Array for that index and retrieve the Raw Text. - Parse that Raw Text into standard AST Nodes and swap them into the Child list in place of the `PositionalNode`. _(Because this happens before Step 3, if `<1>` contained an Unscoped Invocation, it is now safely in the tree waiting to be expanded)._ - TODO: Do `PositionalNode`s handle their own processing (like scaled-back `UnscopedInvocationNode`s) or are they just containers for their parent Invocation to handle? - TODO: What happens if the Positional Invocation returns another raw Positional Invocation, eg if `<Macro|:{<2>}|:arg2>` and the Definition of `Macro` contains `<1>`? Is there a legitimate behavior/use-case here, or are we moreso just trying to prevent and contain malformed user intentions? - TODO: Should Positional Invocations just share the same staging pool strategy for Definitions as Unscoped Invocations? Should those Definitions get hoisted after the Positional Pass so they apply to Unscoped Invocations, or kept staged so they don't?
   _TODO: I'm pretty sure we are supposed to have Top-Level Definitions on the main Context deque by this point since they should apply to the inside of the `UnscopedInvocationNode`s we encounter now (as they are actually a level deeper, we just want to hoist their contents back up to the current level for when we handle Execution)._
   _I think if Step 1 runs through the Token list and Parse the Node-type Tokens into the Child Node List, but just routes the Definition Tokens to a new List in order (or they are left in the List after removing Node Tokens) without actually Parsing them into Definition objects yet, then we could process the `PositionalNode`s in Step 2 without the Parent Top-Level Definitions applied to the Context deque (if that's what we want) and also retain the Strong/Weak information (in the text syntax inside the Definition Tokens) to properly add them to the deque before Step 3 without requiring extra labelling or strength fields._
3. **Unscoped Recursion (`UnscopedInvocationNode` handling):**
    - Scan for `UnscopedInvocationNode`s. For each one, do the following:
    - Trigger Pre-Processing, Resolution, and Expansion (Phases 0, 1B, and 2) on them; or tell them to process themselves which they know to mean those steps.
    - Insert the Nodes from the List it returns directly into the main Child Node List, replacing the `UnscopedInvocationNode`.
    - Extract their returned "Hoisted Definitions" into a local staging pool to prevent them from contaminating sibling nodes during this pass.
4. **Definition Hoisting:** Merge staged Definitions with Top-Level ones.

### The `LocalLibs` Staging Pipeline

_TODO: Update Phase 1B and Phase 2 to reference this process._
To enforce the Proximity of Intent priority hierarchy without relying on complex, multi-dimensional sorting algorithms, the engine utilizes a declarative state-composition pipeline during Node processing.

1. **The `LocalLibs` Array:** Instead of mutating a single local dictionary or directly modifying the `Context` mid-pass, each Parent Node maintains a fixed-size `LocalLibs` array of `DefLibrary` objects (initially `None`). The indices of this array correspond directly to the official Definition Priority Hierarchy (where index 0 is the lowest priority, such as Unscoped Hoisted Definitions, and the highest index is the highest priority, such as Invocation Co-Segments).
2. **Chronological Agnosticism:** The engine processes different definition classes in various passes (e.g., a Lazy Definition pass, an Eager Definition pass, an Unscoped Expansion pass) in a chronological order not matching the priority order. However, the processing logic does not need to know specific priority rules; it simply drops the gathered Definitions from a pass into the corresponding index of the `LocalLibs` array.
3. **The `update_local()` Composition:** Between passes, or before final Execution, the engine calls a unified `update_local()` function. This function:
    - Reverts the Context.DefLibrary to the baseline inherited state (e.g., using a `pop_to_scope()` utility to efficiently strip previous Local Definitions down to the Sentinels).
    - Iterates through the `LocalLibs` array from index 0 to the last index (lowest priority to highest).
    - For each populated index (i.e., `!= None`), it adds those Definitions by calling `Context.DefLibrary.wrap_with(LocalLibs[i])`.
    - This results in rebuilding the last (i.e., the Local) layer of the DefLibrary with every known Definition up to that point, using the preset priority order rather than chronological processing order.

This guarantees that regardless of the order in which definitions are parsed or evaluated, the actual dictionary lookup mathematically enforces the correct priority layers in O(K) appending time.

### Divergence

_Now that the AST is fully expanded and flattened of unscoped elements, the flows diverge based on the Node's structural purpose. Some return back to their Parent now while others continue until producing a final string output._

- `UnscopedInvocationNode` and `PositionalNode` stop here; they bundle all Local (Top-Level and Child) Definitions and the finalized list of Expanded Child Nodes and returns them to its Parent.
    - _TODO: Same as elsewhere, questions about the form of Definitions and merging with Strengths respected._

### Phase 3: Execution Pass

_All of our memory-less objects (Positionals) converted to "standard" form and our state information (Definitions) should now be extracted, leaving just content objects to convert to output text._
_TODO: This phase has not been reviewed and shouldn't be taken as authoritative, just a rough representation._

- **Inject Context:** Push the merged Definitions (from Phase II, Step 4) and the internal Segment Definitions (from Phase I, Step 1) into the Inherited Context so they are active. TODO: Verify Context and Definition states.
- **Execution Walk:** Iterate over the Expanded Child Nodes: creating a strict boundary in the Context Deque, applying Context Pre-Patterns, triggering their own recursive processing, and popping the Scope Sentinal and anything outside of it afterward.
- **Final String Construction:** Concatenate the string results from each of the Child Nodes, then apply Local Post-Patterns and return the final String. _TODO: Is there ever a point the pipeline would reach this point and need to return anything other than a final Literal string?._
- If a Scope Sentinel was pushed in Pre-Processing, ensure it is popped off before returning the Context back to the Parent.
