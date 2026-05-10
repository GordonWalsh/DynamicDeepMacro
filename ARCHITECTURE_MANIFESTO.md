# The Core Architecture Manifesto: Macro Engine System Design

This document serves as the comprehensive, expert-level technical foundation for the Macro Engine. It details the system's structure, processing pipelines, and the strict architectural principles governing its operation. It explicitly documents not only the final design decisions but the specific compiler traps and logical paradoxes that necessitated them.

---

## 1. System Overview & The Eager/Lazy Paradigm

The Macro Engine is a deterministic, context-aware, text-replacement compiler designed to handle highly nested, randomized structural logic. The Macro Engine operates on a phased Evaluation Pipeline, roughly divided into: Pre-Processing (i.e. `LexAndSegment`), Selection or Invocation, Expansion, and Execution

### The Two-Pass Scope Lifecycle

**TODO timing of `PositionalNode`** - I think doing some sort of prepass before the `UnscopedInvocationNode`s in the Expansion Pass. If all `PositionalNode`s are processed before starting on `UnscopedInvocationNode`s, then the Definitions needed for the Positional Invocations can be safely overwritten inside of a `UnscopedInvocationNode`
To satisfy the "Footnote Architecture" (order-independent definitions), the engine utilizes a dual-pass approach over the AST:

1. **Expansion Pass:** A recursive tree-walk targeting non-text-output Nodes, e.g. `UnscopedInvocationNode`s and `PositionalNode`s(?). It triggers Nodes to return Node subtrees to integrate and to modify the Context for the Parent. Hoists Definitions to a staging pool to prevent cross-contamination between Sibling Invocations.
2. **Execution Pass:** A recursive tree-walk targeting Scoped and/or text-output Nodes, e.g. `TextNode`s, `ScopeNode`s, Escape Block Nodes, and `ScopedInvocationNode`s. It triggers these Nodes to perform their internal processing Logic and return a Literal string, which are then all concatenated.

The foundational paradigm of the entire engine is **Breadth-Eager, Depth-Lazy** (Just-In-Time Compilation), via multiple incremental passes over the input data:

- **Breadth-Eager:** At any given step, the engine fully Lexes the flat, zero-depth layer of the current text Payload and Parses it into polymorphic objects.
- **Depth-Lazy:** The engine never Parses or Evaluates the internal contents or structure of an object until it fully recurses into that object.
- _Note: This is a general principal common to most operations, not a hard rule that must be blindly followed._

### Functional Composition & AST Avoidance

The engine prevents AST depth-bloat through Functional Composition rather than literal object wrapping. Explicit `ScopedInvocationNode` and `UnscopedInvocationNode` objects are processed during Execution and Expansion respectively. A Scoped Invocation `<A|B>` is not direct syntactic sugar for a ScopeNode around an Unscoped Invocation object, though it can generally be understood to behave that way. Node objects capture a need for further (potentially recursive) processing, not strictly for objects with Literal Text outputs.
Similarly, Positional Digits (`<0>`) avoid injecting massive overhead into the main Definition dictionary by mapping to a dedicated, ephemeral array on the Context. The Parser outputs a `PositionalNode`, which looks to this array to get a Resolved Value rather than sweeping the Context stack, but otherwise acts similarly to a standard `InvocationNode` logic.

### Eager Evaluation Serialization (The Escape Block Strategy)

"Eager" Definitions (`::Key:Value`) and Argument `::Arg` freeze a dynamic string by Evaluating it immediately at the time of Parsing, utilizing the exact state of the Inherited Context at that point. To prevent the generated Literal Text from undergoing double-evaluation when the Definition is eventually retrieved, the engine serializes the frozen text using the existing explicit Escape Block syntax (`</.../>`).

1. **Evaluation & Escaping:** The engine evaluates the payload, then runs a substitution on the resulting Literal Text to replace any literal `<` and `>` characters with their hexadecimal escape sequence equivalents (`\x3c` and `\x3e`).
2. **Serialization:** The string is wrapped in `</` and `/>` and stored as the Definition's (Raw Text) Value Pattern.
3. **Retrieval Compatibility:** Because the Eager result is serialized as standard engine syntax, it behaves perfectly alongside normal Lazy Values. If an Option is appended later (`::Key:{A|B}`, `:Key>:|C`), the dictionary cleanly resolves the combined Value-Pattern as `</A/>|C`. When Expanded, the Lexer processes the Escape Block, native Python `codecs.decode` unpacks the hex characters, and the output remains safely Literal.

### Regex Pattern Matching as a Substitution Layer

Regex Definitions (`:/pattern/:/replacement/`) do not bypass the standard Macro Engine processing pipeline. They are not a parallel evaluation system; they are strictly a matching and substitution layer operating _within_ the Dictionary Lookup phase.

When `DefLibrary.resolve()` encounters a Regex Value-Pattern in a Definition, it executes a standard `re.sub()` operation from the Regex Key-Pattern or `re.escape()`d plaintext Key (acting as a dynamic, pattern-based equivalent of a simple 'key' -> 'value' string replacement). The string produced by this substitution is treated strictly as **Raw Text**.

- **Dynamic Syntax Construction:** Because Regex outputs Raw Text, it can be used to dynamically generate engine syntax. For example, a definition like `:/wild_(\w+)/:/<pet_\1>/` successfully constructs a new Invocation (`<pet_dog>`), which then flows directly into the standard Phase 2 Expansion Pass to be expanded and executed identically to static input text.

---

## 2. Lexical Analysis (The Lexer) _Content Moved_

This section has been removed to not reproduce and/or conflict with `LEXER_SPECIFICATIONS.md`
TODO Add an up-to-date summary of that content here for continuity.

---

## 3. Interpreting Meaning (The Parser)

The Parser takes the geometric String Views and assigns them semantic meaning by wrapping them in Abstract Syntax Tree (AST) Nodes.

- **Separation of Concerns:** The Lexer defined _where_ the boundaries are; the Parser defines _what_ they do.
- **Atomic Node Payloads:** AST Nodes (like `ScopeNode`, `InvocationNode`, or `TextNode`) do not hold instantiated string Payloads. They hold the `Token` object they were created from, capturing the text content without allocating new memory.

### Polymorphic AST Generation

**Trap Avoided:** Leaving raw `Token` objects for the Evaluator to process procedurally, AND creating unnecessary dummy wrapper nodes.

The Parser converts every execution Token into a strongly typed subclass of a base `ASTNode`. Each subclass has its own internal behavior and is responsible for handling eg Scope and Pre-Patterns.

### No Cross-Contamination

**Trap Avoided:** _Mutating global context during the parsing pass._

Engine objects should not directly edit the processing of sibling objects. If the Parser pushed Definitions to the global Context while building the tree, independent Nodes would modify each other's internal processing unexpectedly based on order.

- **The Solution:** Definitions are typically pushed to staging Libraries, which are then merged with the global Context after a whole pass is complete to allow subsequent object types to reference those changes.

---

## 4. State Management (The Context Stack)

The Context is the engine memory. It is strictly a Data Store; it never executes AST logic. The most complex element of the Context is the Library of in-scope Definitions that may be referenced via Invocations. The behaviors and specifications of this DefLibrary are specified in [DEFINITION_LIBRARY_SPECIFICATION.md](DEFINITION_LIBRARY_SPECIFICATION.md) and not repeated here..

---

## 5. Expansion & Execution (Recursive Walks)

**Trap Avoided:** _Splitting strings before Lexing._ Using Python's `.split('|')` would shatter nested syntax like `<Macro | param:val>`. The Lexer must identify the safe boundaries first.

**Trap Avoided:** _Eager Payload Flattening._ We initially considered eagerly resolving payloads to apply modifiers, but this broke nested hierarchical weights (`A | {B|C}`). Modifiers must be attached to the Invocation key directly (`<2$$key>`) so the engine only splits the top-level buckets, preserving the nested lazy hierarchy.

### Path-Hashed PRNG Determinism

To guarantee that a specific randomized prompt yields the exact same output every time a specific seed is used---even if the prompt is heavily branched---the random state cannot rely on a single global counter. Instead, the branching path leading to each Node is tracked algorithmically (specific method TBD) to modify the base PRNG Seed, so that PRNG calls within a Node (and with the same base Seed) will return consistent results unaffected by structural changes outside of its direct ancestry and Siblings (to avoid repeated PRNG uses in one Node resulting in the same number being drawn).

### The Anonymous Escape Block

TODO this should be a dedicated node type for the Parser to output

**Trap Avoided:** _Global Lexer rules for escape sequences (The Slash Collision Trap)._ Applying `/ /` from Definition Values to all text destroys standard file paths and URLs.

**The Solution:** `/ /` Regex boundaries are restricted entirely to Definition values (to explicitly designate interpreting as Regex instead of as engine syntax).

- To inject an inline escape sequence (like a newline), the engine checks if the Invocation's (by the Parser on a Token?) Payload string ~~(TODO after applying its Parent's Local Pre-Patterns, I think?)~~ starts and ends with `/` (e.g., `</\n/>`).

- If true, it bypasses the Context Stack entirely, strips the slashes, decodes the Unicode escapes natively, and returns the Literal characters. This allows escapes to be dynamically generated by macros while remaining perfectly sandboxed from standard text.

The engine treats standard escape sequences (like `\n`, e.g. in `C:\new_folder`) as generic text. Escape characters are parsed and stripped if they immediately precede a custom engine syntax marker (e.g., `\:` or `\<`). Standard escape sequences only execute natively inside the Escape Block `</.../>` sandbox or within explicitly delimited `/ /` regex patterns in Definitions.

## 6. Additional Technical Definitions & Paradigms

TODO: This section needs to be re-examined and deduplicated. Many of these behaviors are defined elsewhere, many are not being kept up to date, and I'm not sure if it is helpful to list them here.

### I: Lexical Analysis Paradigms

- **Interval-Tracking Speculative Lexer:** A zero-copy lexical scanner that records token boundaries as integer start/end pairs rather than buffering string slices, ensuring $O(N)$ linear time complexity.
- **Zero-Depth Interval Culling:** The resolution algorithm that discards any registered token boundaries that fall strictly within the bounds of a higher-order hierarchy marker, safely neutralizing unbalanced brackets and natively protecting nested syntax.
- **Boundary vs. Discrete Tokenization:** The distinction between paired contextual markers (eg `< >`, `{ }`) which require pushdown-automata tracking, and zero-depth singular markers (`|`, `$$`) which are registered instantly.

### II: Parsing & Structural Paradigms

- **The Grandchild Trap & Base Template Pattern:** The architectural realization that returning parsed sub-trees wrapped in dummy "Block Nodes" creates unnecessary memory bloat and deepens the call stack.
- **Breadth-Eager / Depth-Lazy Parsing:** The engine eagerly builds a polymorphic AST for the current zero-depth scope, but strictly treats all nested macro/group contents as inert raw strings until explicitly invoked.
- **Polymorphic AST Generation:** The parser functions as a Factory, mapping lexed tokens to strongly typed objects (eg TextNode, ScopeNode, Invocation Nodes) that encapsulate their own processing logic to prevent primitive-obsession in global Evaluation logic.
- **Scope Hoisting (Footnote Architecture):** The structural decoupling of State (Definitions) from Data (Outputs) during Parsing, allowing Definitions to be position-independent within their Scope (outside of overriding an earlier Definition).

### III: Evaluation Logic & Option Selection Timing

Option Selection is handled dynamically based on the object type rather than in a unified compiler stage:

- **ScopeNodes (Raw Text):** Perform Option Selection immediately after Lexing to cull unselected branches before Parsing.
- **InvocationNodes (Dictionary Queries):** Do not cull Segments natively. They Lex, Resolve all Segments against the dictionary, and then apply Modifiers to the Resolved Values individually to Select Options.
- **Ephemeral Instantiation:** Child AST branches generated during macro expansion or Group selection are instantiated dynamically, Evaluated, and immediately garbage-collected.
- **Lazy-Evaluation Recursion:** The fundamental guarantee that the Lexer and Parser are invoked as needed (just-in-time compilation), ensuring discarded PRNG branches consume zero parsing cycles.
- **Path-Based PRNG Determinism:** The state-tracking mechanism where a child node's random seed is deterministically computed by its relative position within its Parent, isolating tree branches from sibling's insertions/deletions.
- **Inside-Out Scoped Concatenation:** The principle that nested tree modifiers apply left-to-right while Strong/Weak Scoped Definitions are wrapped with the most global Scope on the inside and most Local on the outside, inherently prioritizing Local Strong and Weak strength declarations over inherited ones (i.e., new Local Definitions become the Strongest/Weakest of the entire Context Definition Library) .
- **Escape Resolution:** The "Anonymous Escape Block" acts before Invocation Payload Evaluation and dictionary-lookup Resolution Logic take place.
    - TODO confirm this behavior or when this check should happen and bypass remaining normal Invocation processing. I.e., do these get Lexed as different Tokens entirely and thus Parsed and processed differently, or just Parsed as different Node types vs other Invocation Tokens and have different internal logic, or some other sort of behavior like a bypass from a ScopedInvocationNode check its complete Payload for the wrapper?.

### IV: Context & State Management Paradigms

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

## 7. Processing Pipeline

- _TODO: Major unknown currently on how exactly the PRNG gets mutated throughout this process_
- **TODO: Review and update for new convert-and-flatten output methodology, instead of repeated string concatenation.**
  This is an overview of the various steps that different Nodes may use to process their contents to return the right type of result for their Node type, or when a piece of Raw Text needs to be Evaluated. A particular Node type may only need to carry out a subset of these steps. This overview attempts to provide a complete list of steps so the reader understands the required order of operations and information flow of the engine, but the actual implementation should have major phases and steps grouped into common functions and internal class logic.

### Phase 0: Pre-Processing

1. If applicable, read the outermost Scope layer (the Parent's Local Definitions) of Context.DefLibrary to get Pre-Patterns and apply them to the Raw Text.
2. If applicable, push a Scope boundary onto Context.DefLibrary to separate Inherited Definitions from new Local ones.
3. If applicable, instantiate the empty LocalLibs List of DefLibrary as all `None`.
4. Lex the internal Payload (or engine input string) into a single long List of Tokens of varying flavors.
   ~~TODO: How does the Lexing function interact with Arguments in Invocation Payloads? Are they a full-on Token Type, or do they get folded into the `DEFINITION` type? Does the Lexer need a flag to tell it whether to detect Arguments? Is there a realistic meaning to non-Definition Argument syntax outside of an Invocation Segment (eg, is it effectively a comment)?~~
    - There is an Invocation flag for the lexer, there are specific Token types for all of Eager and Lazy x Definitions and Arguments. Arguments have no meaning outside Invocation Payloads.

### Transition 1

At this point, we have fully "entered" the Node, and (I think) should be reliant on just the Context object for any engine state information needed. The Payload is now chunked into a List of Tokens ~~(though not 100% on whether that List is flat or pre-Segmented at the detected Split Tokens)~~ for each Segment. The processing pipeline branches into two paths based on whether the Node is Invocation-like or Raw Text content.

### Phase 1A: Selection (Non-Invocations and general Raw Text)

_Invocation-type Nodes would (currently, might be a future feature to add) skip this step and perform the full Resolution Phase instead, but for general Raw Text (eg engine root input) or non-Invocation Node (eg `ScopeNode`) Payloads, this step is performed._
TODO: Are Modifier Separators Interleaved as Tokens or are they Expanded and the Nodes interleaved with Definitions combining somehow? I think the former, for consistency, but may have weird effects?

1. Extract and Parse the Modifier Token from the front of the Token List, or instantiate a default Modifier.
    - Actually, be more generous and check all Segments for starting with a Modifier (use the first one if multiple?).
2. Lex (and Expand if needed? _later note: maybe leave it as Tokens?_) the Separator text from the Modifier.
    - If this requires PRNG Selection itself or produces Definition objects, we just accept that for now. Details TBD?
3. ~~Split the Token List (sans Modifier) into Sublists at the Top-Level `SPLIT` Tokens.~~ Use the Modifier properties and PRNG Seed to pick Segments as needed. TODO exact mathematical/combinatorial logic but let's say we get a list of Segment indices.
4. Interleave the Token Sublists for the Step 3 indices with the Separator Token List from Step 2 to produce one flat List of Tokens combining all Selected Options and Modifier Separators.

### Phase 1B: The Resolution Phase (Invocations Only)

_This section only applies to `ScopedInvocationNode` and `UnscopedInvocationNode`. It is the process of Evaluating the Segmented Raw Key-Strings into their final Evaluated Key form, checking that Evaluated Key against the Definition Library to accumulate Definition Payloads into a single Raw Resolved Value, then combining the unparsed Resolved Values from all Key-Strings together into a single combined starting point to proceed to the next Phase. Due to the nature of the internal operations, these Resolved Values and their combinations may take the form of Lists of Tokens rather than actual string concatenations, but all manipulations occur before Parsing out meaning from those Tokens._
- ~~TODO: I think an Escape Block syntax might get branched this way during processing as well, and if so should have a detection and reroute to that behavior.~~
    - Escape Blocks are now their own `ESCAPE` Tokens, so there should be no confusion with Invocations.

1. ~~Separate the token List at Top-Level `SPLIT` Tokens to get a List of Sublists, each representing one Segment with Modifier still attached.~~ TODO: Something needs to happen with the Segments before they are sorted and mixed around to properly capture the right index for each Positional array element.
    - ~~TODO: It looks like the Segment sub-listing may become part of the Lexer with an "invocation behavior" flag that changes the iteraction between Definitions and Split markers. The Lexing may stay as part of a separate "Phase 0" Pre-Processing or may be absorbed into the Phase 1 of the specific Node logics.~~ Answer: Segmenting is getting absorbed into Lexing. The other part is still TBD.
2. Sort into Raw Keys (not starting with `:`) for now vs Definitions and Positional Arguments (starting with `:`) for later.
    - ~~TODO: How does this all gets coordinated between the Lexer, Parser, and this sorting operation (see Pre-Processing `TODO` above)? Trying to do some weird first-Token-type-of-Segment switch but also check the first character of the Token text (Token's Payload?) would be the wrong setup.~~
        - ~~This might just be handled by the Lexer producing either specific `ARGUMENT` Tokens or allowing invalid/incomplete `DEFINITION` Tokens, whether limited to only Invocation-mode specifically or as a general behavior. Since we will already need the Invocation flag to modify `|` behavior, adding a check for non-Definition leading-`:` strings as the first character or following a `|` (or editing the Definition capture logic to branch to valid and invalid syntax instead of requiring valid) should fit cleanly into our speculative interval-culling architecture. The sorting step here would then just be to Lex + Segment the Payload and then check each Token sublist for being a sole `DEFINITION` or (if applicable) `ARGUMENT` Token and diverting those, while everything else remains a `TEXT`.~~
        - Answer: Yes, the Lexer identifies Arguments. Each Segment sub-List should contain a lone Definition, a lone Argument, or some combination of other Token Types that will Evaluate to the Key.
    - TODO: is it valid to have Modifiers on Definition and especially Argument Segments, and where do they go relative to other syntax? Normally Modifiers are not supposed to go with the Value-Pattern (on the Invocation instead), but should that change in this situation? I don't think we would want to deal with Modifiers in an other-wise single-digit Positional Invocation, for example?
3. **Key-String Evaluation:** Trigger overarching String Evaluation specifically on the Raw Key Segments to resolve dynamic keys (e.g., `<Weapon_<Element>>` -> `Weapon_Fire`).
    - TODO: I'm not sure if it would be be better to Evaluate all Key-Strings first and then Resolve them all, or if it should loop over the Key-String Segments and do Evaluation and Resolution immediately on each.
    - TODO These would have already been Lexed to (content-like, not Definition-like) Tokens, so ideally the Evaluation would continue forward from there instead of repeating.
4. **Resolution:** Use `Context.DefLibrary.resolve()` on the Evaluated Keys to get a Raw Resolved Value (either as a string or as a Lexed Token List (of Lists)) for each.
    - I think the answer WRT type is going to be as a single (Raw `TEXT`?) Token, which could be a root string slice if the Resolution was simple, but may need to be constructed if it was not.
5. **Selection:** For each Resolved Value, (first Lex if needed, then) use the associated Modifier from the original Segment or default to single random Option to Apply PRNG Selection to get a flat Token List.
    - With the loosening of the locational requirements on Modifiers for non-Invocation-Payload Raw Text (e.g. the Resolved Value), I think the Modifier Token that was peeled off from the Key-Segment can just be appended to the front of the Resolved Value's Lexed Token List, where it would take precedence and cause any remaining Modifiers to be silently overwritten. Specifically appended as a Token though, or else it could incorrctly merge with a Value's "native" Modifier.
6. **Consolidation:** Join the Selected Token Lists from each Key Segment into a single final flat List. Since the Selection was already performed on each Segment individually, there shouldn't be any Top-Level Splits left to worry about (unless deliberately reintroduced by custom Modifer Separator, but TODO we'll examine that edge case behavior later).
7. **Definition Loading:** Take the inert Positional Arguments and Definition Values identified in Step 1 and load them into the current Context's flat Positional array/List so they are ready for Phase 2. Also load the Segment Definitions into the applicable LocalLibs index (TBD might be handled natively by the Parser by optionally passing in the "Library to fill" explicitly, could be defaulted to the DefLibrary of the Context that's passed in). (Tentative: may change) Also load the Evaluated Keys into the Positional array/List as referencable Values.
    - TODO Answer: Definitions would be handled by a separate Definition Token handler function, not the Token -> Node Parser, that does take in a DefLibrary reference to fill and Context for Evaluation, if needed.

_In processing `PositionalNode`s, there are no Key-Strings or other Segments to worry about, they will only match the single Definition for their index, and they do not load Positional Definitions for Children. Since almost all of the complex behavior handled by the `DefLibrary.Resolve` function is not necessary (and to avoid requiring a DefLibrary per index or adding get-by-index to DefLibrary), they can just directly access their Positional Definition from the Context array and use its Value-Pattern as the Resolved Value, then apply Selection if needed._

### Transition 2

We now have one flat List of Tokens containing everything that will go towards creating the output text, with Definition substitutions for Invocations applied, and all non-Selected Options removed. Ensure any Context changes that need to be made before Phase 2 are completed before this point.

### Phase 2: The Common Expansion Process

This is a multi-step process that sweeps over the Token List multiple times, looking for different Token Types, to build up the Local Context state in preparation for the complete recursion in the next phase. Each sweep modifies a specific staging DefLibrary in a LocalLibs List; at the end of each sweep, the Context DefLibrary is refreshed by removing the previous Local changes and re-merging all of the LocalLibs back in, ensuring that their priorities relative to each other are maintained.

TODO: LocalLibs integration.
TODO: ~~It's probably been (maybe inaccurately) described elsewhere, but the exact behavior of how the Parser interacts with Definitions (easpecially Eager ones) and how they then get absorbed into the relevant DefLibrary needs to be detailed. I've assumed that the Parser will potentially modify a DefLibrary that is passed in.~~
_This is a standardized AST tree-walk and where Invocation-type Nodes and non-Invocation Nodes should merge back together. It starts with a flat Token List from a Phase 1 operation, whether a 1A Selection or a 1B Resolution, but it is exactly the same pass performed on both regardless of origin. A Resolution process may have altered the Context object or populated some initially-empty containers, but the Expansion should be able to handle either case without needing separate functions or anything._

1. **Handle Lazy Defs and Split Tokens:** Simultaneously processes the first item sweep, Lazy Definitions, while preparing for the subsequent ones. Walk the Token List, branching on Token type: Send each Lazy Definition to the Definition Token handler function (TBD, pseudocoded in def_lib_specs) with the relevand LocalLib indexed item passed, Context unneeded. Send Eager Definition Tokens to a temporary list. Send all AST Node type Tokens to an AST Token List. Split and Modifier Tokens should already have been processed and removed by now, and Argument Tokens should also have been handled, but ignore any of these found. Refresh Local Context.

2. **Eager Definitions:** Walk the temporary Eager Definition Token List, send each one to the Definition Token handler with the correct LocalLib and _with_ the with-Lazy Context. Refresh Local Context.

3. **Parsing:** Parse the AST Token List into a list of Child AST Nodes ~~and Top-Level Definitions. TODO: Definition handling as emitted objects or by modifying a passed DefLibrary? Elaborated elsewhere~~.
   _TODO: I'm not sure if Top-Level Definitions (Step 1) should be applied to Positionals, since they are retrieving content from "above" that (the Parent Invocation's Segments), but then there's maybe inconsistency with by-index vs by-name Invocations of Parent Definition Segments?_
4. **Positional Early-Capture (`PositionalNode` handling):**
    - Scan the top-level Child list for `PositionalNode`s (e.g., `<1>`).
    - Query the Positional Array for that index and retrieve the Raw Text.
    - Parse that Raw Text into standard AST Nodes and swap them into the Child list in place of the `PositionalNode`. _(Because this happens before Step 3, if `<1>` contained an Unscoped Invocation, it is now safely in the tree waiting to be expanded)._
    - TODO: Do `PositionalNode`s handle their own processing (like scaled-back `UnscopedInvocationNode`s) or are they just containers for their parent Invocation to handle?
    - TODO: What happens if the Positional Invocation returns another raw Positional Invocation, eg if `<Macro|:{<2>}|:arg2>` and the Definition of `Macro` contains `<1>`? Is there a legitimate behavior/use-case here, or are we moreso just trying to prevent and contain malformed user intentions?
    - ~~TODO: Should Positional Invocations just share the same staging pool strategy for Definitions as Unscoped Invocations? Should those Definitions get hoisted after the Positional Pass so they apply to Unscoped Invocations, or kept staged so they don't?~~
        - Resolved by LocalLibs implementation.
    - ~~TODO: I'm pretty sure we are supposed to have Top-Level Definitions on the main Context deque by this point since they should apply to the inside of the `UnscopedInvocationNode`s we encounter now (as they are actually a level deeper, we just want to hoist their contents back up to the current level for when we handle Execution).~~
    - _I think if Step 1 runs through the Token list and Parse the Node-type Tokens into the Child Node List, but just routes the Definition Tokens to a new List in order (or they are left in the List after removing Node Tokens) without actually Parsing them into Definition objects yet, then we could process the `PositionalNode`s in Step 2 without the Parent Top-Level Definitions applied to the Context deque (if that's what we want) and also retain the Strong/Weak information (in the text syntax inside the Definition Tokens) to properly add them to the deque before Step 3 without requiring extra labelling or strength fields._
5. **Unscoped Recursion (`UnscopedInvocationNode` handling):**
    - Scan for `UnscopedInvocationNode`s. For each one, do the following:
    - Trigger Pre-Processing, Resolution, and Expansion (Phases 0, 1B, and 2) on them; or tell them to process themselves which they know to mean those steps.
    - Insert the Nodes from the List it returns directly into the main Child Node List, replacing the `UnscopedInvocationNode`.
        - TODO This might be a point where `UnscopedInvocationNode` has a processing/conversion method that differs from the others, in that it returns unprocessed Nodes instead of Evaluated output Nodes.
    - Extract their returned "Hoisted Definitions" the correct LocalLib to prevent them from contaminating sibling nodes during this pass. Refresh Local Context when complete.
    - TODO What strategy is used to build up the Context so that contained Invocations can reference contained Definitions, but not prematurely leak to other Unscoped Invocations? Is it as simple as just pushing scope when entering like with other nodes, but then the collected Definitions from the recursive Expansion get re-added? Maybe the outermost scope layer of the Context DefLibrary _is_ the vehicle that the Hoisted Definitions ride back up, but they get stripped off and moved to the staging Library before moving to the next sibling UnscopedInvocationNode.

### The `LocalLibs` Staging Pipeline

To enforce the Proximity of Intent priority hierarchy without relying on complex, multi-dimensional sorting algorithms, the engine utilizes a declarative state-composition pipeline during Node processing.

1. **The `LocalLibs` Array:** Instead of mutating a single local dictionary or directly modifying the `Context` mid-pass, each Parent Node maintains a fixed-size `LocalLibs` array of `DefLibrary` objects (initially `None`). The indices of this array correspond directly to the official Definition Priority Hierarchy (where index 0 is the lowest priority, such as Unscoped Hoisted Definitions, and the highest index is the highest priority, such as Invocation Co-Segments).
2. **Chronological Agnosticism:** The engine processes different definition classes in various passes (e.g., a Lazy Definition pass, an Eager Definition pass, an Unscoped Expansion pass) in a chronological order not matching the priority order. However, the processing logic does not need to know specific priority rules; it simply drops the gathered Definitions from a pass into the corresponding index of the `LocalLibs` array.
3. **The `update_local()` Composition:** Between passes, or before final Execution, the engine calls a unified `update_local()` function. This function:
    - Reverts the Context.DefLibrary to the baseline inherited state (e.g., using a `pop_to_scope()` utility to efficiently strip previous Local Definitions down to the Sentinels).
    - Iterates through the `LocalLibs` array from index 0 to the last index (lowest priority to highest).
    - For each populated index (i.e., `!= None`), it adds those Definitions by calling `Context.DefLibrary.wrap_with(LocalLibs[i])`.
    - This results in rebuilding the last (i.e., the Local) layer of the DefLibrary with every known Definition up to that point, using the preset priority order rather than chronological processing order.
    - _TODO this function is currently a method of the `DefLibrary` class, not sure if that's better or if it should be external._

This guarantees that regardless of the order in which definitions are parsed or evaluated, the actual dictionary lookup mathematically enforces the correct priority layers in O(K) appending time.

### Divergence

_Now that the AST is fully expanded and flattened of unscoped elements, the flows diverge based on the Node's structural purpose. Some return back to their Parent now while others continue until producing a final string output._

- `UnscopedInvocationNode` and `PositionalNode` stop here; they bundle all Local (Top-Level and Child) Definitions and the finalized list of Expanded Child Nodes and returns them to its Parent.
    - _TODO: Same as elsewhere, questions about the exact form of Definition transfer, returned DefLibrary vs mutated staging vs implicit Context.DefLibrary scoping behavior._

### Phase 3: Execution Pass

_All of our memory-less objects (Positionals) converted to "standard" form and our state information (Definitions) should now be extracted, leaving just content objects to convert to output text._
_TODO: This phase has not been 100% reviewed and shouldn't be taken as authoritative, but should be accurate._

TODO: Verify Context and Definition states are correct, but previous steps should have set them all up.

- **Execution Walk:** Iterate over the Expanded Child Nodes and trigger their internal Execution processing to convert them into output-ready Nodes. Each Node type is responsible for managing its own Unbounded Pattern application and cleaning up the Context before returning to the Parent, as described in Pre-Processing.
- **Output Flattening:** Flatten the Executed Child Nodes into a single List of output-ready Nodes (ie, I think, TextNodes with `LITERAL` `Token` Payloads).
- **Post-Pattern Application:** If there are any Local Post-Patterns to apply, then the Flattened Executed Child Nodes need to be Serialized to a single string. `Token`ized slices of this string can be interleaved with individual Pattern match result `Token`s to efficiently create a new output (Child) List of `LITERAL` type `TextNode`s.
- If any changes were made to the Context that need to be cleaned up, now is the time. The flat output-ready Child Node list is returned back to the parent/caller to be flattened together with other Nodes or to be Serialized to a string result if this was the root Node emitting to the outer Evaluation process instead of another Parent Node.
