# Core Features & Behaviors (User UX)

This document defines the fundamental behaviors of the Macro Engine from the user's perspective. It strictly describes what happens to Raw input text as it passes through the engine to become finished Literal text, serving as the functional blueprint for the user experience.

1. **Plaintext Pass-Through:** Standard text and unrecognized syntax are ignored and passed through to the output perfectly intact.

2. **Bounded Macros (Key-Value Replacement):** A user defines a key (`:key:value`). Whenever `<key>` is written in the text, it is replaced by `value`.

3. **Constructed Keys (Dynamic Invocation):** Users can build invocation keys dynamically. For example, `<Weapon_<Element>>` will first evaluate `<Element>` into a literal string, e.g., `Fire`, and then invoke the resulting key, i.e., `<Weapon_Fire>`.

4. **Isolated Execution Groups:** Wrapping text in `{ }` isolates the contents to be processed (eg lexed, parsed, expanded, and executed) as an independent unit/child-scope before participating in the parent string's syntax.

5. **Evaluation Timing:** The engine avoids complex caching algorithms by offering two native Definition and Argument behaviors:
    - Lazy (Dynamic) Definitions (`:Key:{Alice|Bob}`) and Arguments (`<Key|:{Alice|Bob}>`) are kept as Raw Text. They re-evaluate and re-roll the PRNG on every Invocation.
    - Eager (Frozen) Definitions (`::Key:{Alice|Bob}`) and Arguments (`<Key|::{Alice|Bob}>`) have their Value-Pattern/Text Evaluated using the Context at Definition, with only the result saved. The PRNG rolls once, yielding a Literal String (e.g., `Alice`), and every Invocation will result in the same Literal Resolution. The value is natively permanently frozen.
    - *Note on Acceptable Loss:* Because Eager definitions freeze text, appending options to them later (e.g., `>:Key:|Charlie`) will append to the frozen literal, yielding `Alice|Charlie`. The engine does not "mind-read" intent to un-evaluate a frozen option pool.
    - *Note: It is tentatively planned that Eager Evaluation results are `re.escape()`'d before saving to the Definition object, and flag the Value as Regex. This reproduces the exact Literal Text without re-evaluating the Definition Value, bypassing the need for a separate Raw/Literal Definition field.*

6. **Segments in Invocations** can be Key-Strings (no leading `:`), Definitions (leading `:` and valid syntax), or Arguments (leading `:` but not Definition syntax).
    - **Arguments** can be passed lazily (default, preceded by `:`) or eagerly (preceded by `::`), matching Definition behavior. Lazy Arguments (and Lazy Definitions) store Raw Text/Values and Evaluate independently upon each Invocation. Eager Arguments (and Eager Definitions) are explicitly evaluated into Literal Text before being stored, locking in PRNG results.

7. **Positional Digit Invocations** Users can reference Parent Invocation Segments using zero-indexed digit Positional Invocations (e.g., `<0>`, `<1>`). These digits bind strictly to a separate, flat array of Definitions. This array has no memory and changes every time the engine enters a new Invocation, regardless of primary Scope changes.
    - **Positional Invocations** for Key-Strings return Evaluated Key-Strings, subject to default non-matched Key-String behavior (i.e., may insert text in the output).
    - **Positional Invocations** for a Definition Segment return the Value of the Definition just as if its Key was Invoked (albeit with empty captures for Regex-Regex Definitions).
    - **Positional Invocations** for Arguments will return the Text of the Argument following all the normal behaviors of a Definition Value-Pattern (note: capture group references in Regex-type Value Patterns will not be populated since there is no actual Key-String for the Definition Key-Pattern to match against). Arguments never directly become output text without being explicitly Invoked.

8. **Scoped Invocations (Segment Sharing)** Processing an Invocation with multiple Segments (`<macro|:key:val|container|:positional>`) creates an isolated environment. The Segments provided act as temporary Local Definitions, expanded macros with applicable Definitions, or positional Raw Values that apply *only* during the execution of this Invocation and do not leak to the surrounding text. Internally, this is structurally mapped as an Unscoped Invocation encapsulated within a Scope Node boundary, which provides the PRNG and Scope isolation intrinsically.

9. **Unscoped Invocations (Scope Injection)** Processing an Invocation with a leading Split marker (`<|container|:key:val>`) does *not* isolate the contents and provides its resulting Nodes and contained Definitions to the parent Scope. This allows macros to act as Definition Containers whose rules seamlessly apply to their siblings.

10. **Multi-Value Randomization** Separating items with a split token inside a group (`{A|B|C}`) randomly selects and outputs a single winning option.

11. **Selection Modifiers** Prefixing a group or invocation with a logic modifier (e.g., `2$$`) alters the randomization behavior—such as picking multiple options, ensuring uniqueness, or applying specific separators.

12. **Deterministic Randomness (Path-Dependent PRNG)** Random selections are tied to a specific seed and their path in the syntax tree. Adding or removing a randomized invocation in one part of the text will not change the outcomes of unrelated invocations, but invoking the exact same Key multiple times will produce appropriately varied results.

13. **Evaluation Trace** The engine silently records the decision-path of randomized option selections during generation. Users can query this Trace object after evaluation is complete to see exactly which options were selected without having to reverse-engineer the final output string or repeat the recursive walk.

14. **Order Independence (Footnotes)** A user can write a macro definition anywhere in a text block, and it will correctly apply to an invocation anywhere else in that same block, regardless of their relative top-to-bottom order.

15. **Directional Concatenation** Instead of overwriting a definition, a user can append (`>:`) or prepend (`<:`) text to an existing macro's value. **Note:** Interactions between Regex Values and non-Regex Left-/Right-Definitions (or vice versa) require further exploration of desired outcome behavior to resolve the tension between different Evaluation directions. E.g., when do they get combined, should the result be Evaluated or not, etc.

16. **Priority / Strength** A user can define "Strong" overrides (`:`) that take absolute precedence, or "Weak" fallbacks (`::`) that only apply if no Strong definition exists.

17. **Multi-Line Blocks** Users can explicitly wrap massive, multi-line text payloads containing newlines inside `<<` and `>>` to safely assign them to a definition without breaking formatting. This is the primary method for constructing "Container Macros" that hold multiple nested definitions.

18. **Global Text Filters (Pre-/Post-Patterns)** Users can define rules that run *before* the engine processes the text (`:<`) to alter raw syntax, or *after* the engine finishes (`:>`) to apply final formatting/cleanup to the literal output. At each level, new Local Pre-Patterns will be applied to the contents of each Child Payload before further processing (since we can't detect the Local Pre-Patterns and *then* apply them to the Parent Text *before* we did the detection). All in-Scope Pre-Patterns (Global + Local) are applied to to Raw Text Values from Invocation Resolution, since they didn't have the whole Stack of Pre-Patterns applied incrementally at different Payload Depth levels. Local Post-Patterns are applied after Child Node Texts are returned and concatenated, immediately before the Parent Node returns its output string to *its* Parent's Execution. By operating this way, each applicable Pre- or Post-Pattern is scanned exactly once over each character of text (except for Definition Values being affected by Pre-Patterns both as the Raw Text that created the Definition and again at Invocation after being substituted in Resolution, but that was currently deemed an acceptable deviation vs Pre-Patterns present at the time of Invocation but not Definition not affecting Resolved Values, and not trying to do some Scope Depth tracking to selectively apply rules but TODO on checking that last strategy since it should be a single Depth index to track and with the strict Parent-Child inheritance might actually be near-trivial to implement).
TODO clean up this entry re UX behaviors vs implementation details

19. **Regex Pattern Matching** Orthogonal to other Definition syntax variations, any Definition Key or Value wrapped in `/ /` is treated as a Regular Expression, allowing for dynamic search-and-replace rules rather than exact string matching.

20. **Inline Escaping** A user can prevent the engine from interpreting a syntax character by preceding it with a backslash (e.g., `\<` or `\:`), forcing the engine to treat it as a literal character.

21. **Anonymous Escapes** A user can safely inject raw formatting characters (like unparsed colons, brackets, newlines, or specific Unicode characters) into the final text without triggering engine syntax by wrapping them in the explicit escape block `</ ... />`.

## Future Features Planned

- **Direct PRNG Seed Setting:** A feature allowing direct setting of the PRNG Seed mutation (added to the root user input seed) instead of automatic path/index-based mutation, likely implemented as part of the Modifier syntax.
- **Streamlined Modifiers & Legacy Translation:** A streamlined Modifier syntax, accompanied by a user-switch that injects Pre-Patterns to dynamically update old syntax for backwards compatibility without forking the syntax tree.
