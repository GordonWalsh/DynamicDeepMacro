# Core Features & Behaviors (User UX)

This document defines the fundamental behaviors of the Macro Engine from the user's perspective. It strictly describes what happens to Raw input text as it passes through the engine to become finished Literal text, serving as the functional blueprint for the user experience.

**1. Literal Pass-Through** Standard text and unrecognized syntax are ignored and passed through to the output perfectly intact.

**2. Bounded Macros (Key-Value Replacement)** A user defines a key (`:key:value`). Whenever `<key>` is written in the text, it is replaced by `value`.

**3. Constructed Keys (Dynamic Invocation)** Users can build invocation keys dynamically. For example, `<Weapon_<Element>>` will first evaluate `<Element>` into a literal string, e.g., `Fire`, and then invoke the resulting key, i.e., `<Weapon_Fire>`.

**4. Isolated Execution Groups** Wrapping text in `{ }` isolates the contents to be evaluated (lexed, parsed, and executed) as an independent unit/child-scope before participating in the parent string's syntax.

**5. Positional Digit Invocations** Users can reference Parent Invocation Segments using zero-indexed digit Invocations (e.g., `<0>`, `<1>`, `<2>`) in definitions. Key-String Segments return their Evaluated form, Definition Segments return their Value, and initial `:` Segments that aren't valid Definitions return the Raw text following the `:`.

**6. Scoped Invocations (Segment Sharing)** Executing an invocation with multiple segments (`<macro|:key:val|container|:positional>`) creates an isolated environment. The segments provided act as temporary local definitions, expanded macros with applicable definitions, or positional values that apply _only_ during the execution of this invocation and do not leak to the surrounding text.

**7. Unscoped Invocations (Scope Injection)** Executing an invocation with a leading split marker (`<|container|:key:val>`) does _not_ isolate the contents and injects its resulting text and contained definitions directly into the parent scope. This allows macros to act as Definition Containers whose rules seamlessly apply to their siblings.

**8. Multi-Value Randomization** Separating items with a split token inside a group (`{A|B|C}`) randomly selects and outputs a single winning option.

**9. Selection Modifiers** Prefixing a group or invocation with a logic modifier (e.g., `2$$`) alters the randomization behavior—such as picking multiple options, ensuring uniqueness, or applying specific separators.

**10. Deterministic Randomness (Path-Dependent PRNG)** Random selections are tied to a specific seed and their execution path in the syntax tree. Adding or removing a randomized invocation in one part of the text will not change the outcomes of unrelated invocations, but invoking the exact same Key multiple times will produce appropriately varied results.

**11. Execution Trace** The engine silently records the decision-path of randomized option selections during generation. Users can query this Trace object after evaluation is complete to see exactly which options were selected without having to reverse-engineer the final output string.

**12. Order Independence (Footnotes)** A user can write a macro definition anywhere in a text block, and it will correctly apply to an invocation anywhere else in that same block, regardless of their relative top-to-bottom order.

**13. Directional Concatenation** Instead of overwriting a definition, a user can append (`>:`) or prepend (`<:`) text to an existing macro's value.

**14. Priority / Strength** A user can define "Strong" overrides (`:`) that take absolute precedence, or "Weak" fallbacks (`::`) that only apply if no Strong definition exists.

**15. Multi-Line Blocks** Users can explicitly wrap massive, multi-line text payloads containing newlines inside `<<` and `>>` to safely assign them to a definition without breaking formatting. This is the primary method for constructing "Container Macros" that hold multiple nested definitions.

**16. Global Text Filters (Pre/Post Patterns)** Users can define rules that run _before_ the engine processes the text (`:<`) to alter raw syntax, or _after_ the engine finishes (`:>`) to apply final formatting/cleanup to the literal output.

**17. Regex Pattern Matching** Orthogonal to other Definition syntax variations, any Definition Key or Value wrapped in `/ /` is treated as a Regular Expression, allowing for dynamic search-and-replace rules rather than exact string matching.

**18. Inline Escaping** A user can prevent the engine from interpreting a syntax character by preceding it with a backslash (e.g., `\<` or `\:`), forcing the engine to treat it as a literal character.

**19. Anonymous Escapes** A user can safely inject raw formatting characters (like unparsed colons, brackets, newlines, or specific Unicode characters) into the final text without triggering engine syntax by wrapping them in the explicit escape block `</ ... />`.
