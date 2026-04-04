import unittest
from macro_engine import PromptEngine, MacroContext, Definition
from lexer import lex_with_boundaries, Token


def wrap_literal_tokens(items):
    """
    Convert list of strings to list of literal Tokens for test comparison.
    
    Allows test expectations to be written as plain strings while comparing
    against Token objects. A literal Token has marker_type=('', '').
    
    Args:
        items: List of strings and/or Token objects
    
    Returns:
        List of Token objects, with strings converted to literal tokens
    """
    return [
        Token(start_idx=0, end_idx=0, marker_type=('', ''), text=item) 
        if isinstance(item, str) 
        else item 
        for item in items
    ]


class TestLexWithBoundaries(unittest.TestCase):
    """Test suite for the lex_with_boundaries() tokenizer function."""

    def test_literal_text_only(self):
        """Verify that plain text with no boundaries is returned as a single element."""
        result = lex_with_boundaries("hello world")
        self.assertEqual(result, wrap_literal_tokens(["hello world"]))

    def test_single_bounded_token(self):
        """Verify basic bounded token detection with single boundary type."""
        result = lex_with_boundaries("hello <world>", [('<', '>')])
        expected = wrap_literal_tokens(["hello "]) + [Token(0, 0, ('<', '>'), "<world>")]
        self.assertEqual(result, expected)

    def test_multiple_bounded_tokens_same_type(self):
        """Verify multiple tokens of the same boundary type."""
        result = lex_with_boundaries("The <color> <animal> ran", [('<', '>')])
        expected = wrap_literal_tokens(["The "]) + [Token(0, 0, ('<', '>'), "<color>")] + wrap_literal_tokens([" "]) + [Token(0, 0, ('<', '>'), "<animal>")] + wrap_literal_tokens([" ran"])
        self.assertEqual(result, expected)

    def test_multiple_boundary_types(self):
        """Verify handling of multiple boundary types with priority."""
        result = lex_with_boundaries("hello <world> and {test} end", [('<', '>'), ('{', '}')])
        expected = (wrap_literal_tokens(["hello "]) + [Token(0, 0, ('<', '>'), "<world>")] + 
                    wrap_literal_tokens([" and "]) + [Token(0, 0, ('{', '}'), "{test}")] + 
                    wrap_literal_tokens([" end"]))
        self.assertEqual(result, expected)

    def test_boundary_priority(self):
        """Verify that first boundary tuple in list has priority."""
        # If < > has priority, it should match before { }
        result = lex_with_boundaries("a <b> c", [('<', '>'), ('{', '}')])
        expected = wrap_literal_tokens(["a "]) + [Token(0, 0, ('<', '>'), "<b>")] + wrap_literal_tokens([" c"])
        self.assertEqual(result, expected)

    def test_boundary_at_string_start(self):
        """Verify token at the start of the string."""
        result = lex_with_boundaries("<start> of text", [('<', '>')])
        expected = [Token(0, 0, ('<', '>'), "<start>")] + wrap_literal_tokens([" of text"])
        self.assertEqual(result, expected)

    def test_boundary_at_string_end(self):
        """Verify token at the end of the string."""
        result = lex_with_boundaries("end of <text>", [('<', '>')])
        expected = wrap_literal_tokens(["end of "]) + [Token(0, 0, ('<', '>'), "<text>")]
        self.assertEqual(result, expected)

    def test_consecutive_boundaries(self):
        """Verify consecutive tokens with no literal text between them."""
        result = lex_with_boundaries("<first><second>", [('<', '>')])
        expected = [Token(0, 0, ('<', '>'), "<first>"), Token(0, 0, ('<', '>'), "<second>")]
        self.assertEqual(result, expected)

    def test_nested_boundaries_same_type(self):
        """Verify that nested boundaries of the same type are kept as flat content."""
        result = lex_with_boundaries("text <outer <inner> content>", [('<', '>')])
        # <inner> should be treated as literal content, not a separate token
        expected = wrap_literal_tokens(["text "]) + [Token(0, 0, ('<', '>'), "<outer <inner> content>")]
        self.assertEqual(result, expected)

    def test_nested_boundaries_different_types(self):
        """Verify that mixed nested boundaries are preserved as flat content."""
        result = lex_with_boundaries("a <outer {inner} content>", [('<', '>'), ('{', '}')])
        # {inner} should not trigger a split; it's nested inside <>
        expected = wrap_literal_tokens(["a "]) + [Token(0, 0, ('<', '>'), "<outer {inner} content>")]
        self.assertEqual(result, expected)

    def test_empty_boundary(self):
        """Verify that empty boundaries are kept as valid tokens."""
        result = lex_with_boundaries("text <> more", [('<', '>')])
        expected = wrap_literal_tokens(["text "]) + [Token(0, 0, ('<', '>'), "<>")] + wrap_literal_tokens([" more"])
        self.assertEqual(result, expected)

    def test_unclosed_boundary_end_of_string(self):
        """Verify that unclosed boundary at end of string is treated as literal."""
        result = lex_with_boundaries("text unclosed<", [('<', '>')])
        self.assertEqual(result, wrap_literal_tokens(["text unclosed<"]))

    def test_unclosed_boundary_with_following_text(self):
        """Verify that unclosed boundary with following text is emitted as literal."""
        result = lex_with_boundaries("text <unclosed more", [('<', '>')])
        self.assertEqual(result, wrap_literal_tokens(["text <unclosed more"]))

    def test_extra_closing_marker(self):
        """Verify that extra closing markers are treated as literal text."""
        result = lex_with_boundaries("text > unmatched", [('<', '>')])
        self.assertEqual(result, wrap_literal_tokens(["text > unmatched"]))

    def test_escape_opening_marker(self):
        """Verify that escaped opening marker is treated as literal."""
        result = lex_with_boundaries(r"text \<not a token\>", [('<', '>')])
        self.assertEqual(result, wrap_literal_tokens([r"text \<not a token\>"]))

    def test_escape_closing_marker(self):
        """Verify that escaped closing marker inside token prevents token closure."""
        result = lex_with_boundaries(r"text <content\> still inside>", [('<', '>')])
        expected = wrap_literal_tokens(["text "]) + [Token(0, 0, ('<', '>'), r"<content\> still inside>")]
        self.assertEqual(result, expected)

    def test_escape_backslash(self):
        """Verify that escaped backslash is treated as literal."""
        result = lex_with_boundaries(r"text \\ not escaped", [('<', '>')])
        self.assertEqual(result, wrap_literal_tokens([r"text \\ not escaped"]))

    def test_backslash_before_non_syntax_char(self):
        """Verify that backslash before non-syntax character is kept as-is."""
        result = lex_with_boundaries(r"text \a literal", [('<', '>')])
        self.assertEqual(result, wrap_literal_tokens([r"text \a literal"]))

    def test_custom_single_char_boundaries(self):
        """Verify function works with custom boundary markers."""
        result = lex_with_boundaries("text [bracket] content", [('[', ']')])
        expected = wrap_literal_tokens(["text "]) + [Token(0, 0, ('[', ']'), "[bracket]")] + wrap_literal_tokens([" content"])
        self.assertEqual(result, expected)

    def test_multiple_custom_boundaries(self):
        """Verify multiple custom boundary types with priority."""
        result = lex_with_boundaries(
            "a [b] c (d) e",
            [('[', ']'), ('(', ')')]
        )
        expected = (wrap_literal_tokens(["a "]) + [Token(0, 0, ('[', ']'), "[b]")] + 
                    wrap_literal_tokens([" c "]) + [Token(0, 0, ('(', ')'), "(d)")] + 
                    wrap_literal_tokens([" e"]))
        self.assertEqual(result, expected)

    def test_default_boundaries(self):
        """Verify that default boundaries are { } and < > with { } priority."""
        result = lex_with_boundaries("a <b> c {d} e")
        # Default is [( '{', '}'), ('<', '>')], so { } has priority
        expected = (wrap_literal_tokens(["a "]) + [Token(0, 0, ('<', '>'), "<b>")] + 
                    wrap_literal_tokens([" c "]) + [Token(0, 0, ('{', '}'), "{d}")] + 
                    wrap_literal_tokens([" e"]))
        self.assertEqual(result, expected)

    def test_complex_nested_structure(self):
        """Verify complex nesting with multiple boundary types."""
        result = lex_with_boundaries(
            "start <outer [nested] {mixed} end> final",
            [('<', '>'), ('[', ']'), ('{', '}')]
        )
        # Everything inside <> should be preserved as flat content
        expected = (wrap_literal_tokens(["start "]) + 
                    [Token(0, 0, ('<', '>'), "<outer [nested] {mixed} end>")] + 
                    wrap_literal_tokens([" final"]))
        self.assertEqual(result, expected)

    def test_multiple_unclosed_at_end(self):
        """Verify multiple unclosed boundaries are emitted together as literal."""
        result = lex_with_boundaries("text <unclosed {also", [('<', '>'), ('{', '}')])
        self.assertEqual(result, wrap_literal_tokens(["text <unclosed {also"]))

    def test_interleaved_boundaries_outer_consumes_inner(self):
        """Verify that when boundaries interleave, the outer boundary consumes the inner."""
        # <foo {bar> } has angle at 0-9, brace at 5-11, brace is consumed by angle
        result = lex_with_boundaries("<foo {bar> }", [('<', '>'), ('{', '}')])
        # Expected: single token <foo {bar> with brace consumed as content, literal " }"
        expected = [Token(0, 0, ('<', '>'), "<foo {bar>")] + wrap_literal_tokens([" }"])
        self.assertEqual(result, expected)

    def test_interleaved_angle_priority_consumes_brace(self):
        """Verify interleaved boundaries with angle priority.
        
        String: <a {b> }
        With angle priority, angle [0,5] consumes the { marker.
        Brace { is inside angle token, } is outside → } becomes literal.
        Expected: angle token <a {b>, literal text  }
        """
        result = lex_with_boundaries("<a {b> }", [('<', '>'), ('{', '}')])
        expected = [Token(0, 0, ('<', '>'), "<a {b>")] + wrap_literal_tokens([" }"])
        self.assertEqual(result, expected)

    def test_interleaved_brace_priority_consumes_angle(self):
        """Verify interleaved boundaries with brace priority.
        
        String: <a {b> }
        With brace priority, brace [3,7] consumes the < marker.
        Angle < is outside brace token (at 0), > is inside → < becomes literal.
        Expected: literal text <a , brace token {b> }
        """
        result = lex_with_boundaries("<a {b> }", [('{', '}'), ('<', '>')])
        expected = wrap_literal_tokens(["<a "]) + [Token(0, 0, ('{', '}'), "{b> }")]
        self.assertEqual(result, expected)

    def test_interleaved_angle_before_brace_angle_priority(self):
        """Verify interleaved boundaries where angle opens first.
        
        String: <{b> }
        Angle opens at 0, brace opens at 1, angle closes at 4.
        Angle [0,4] consumes the { marker. Brace } at 6 becomes literal.
        Expected: angle token <{b>, literal text  }
        """
        result = lex_with_boundaries("<{b> }", [('<', '>'), ('{', '}')])
        expected = [Token(0, 0, ('<', '>'), "<{b>")] + wrap_literal_tokens([" }"])
        self.assertEqual(result, expected)

    def test_interleaved_brace_before_angle_brace_priority(self):
        """Verify interleaved boundaries where brace opens first.
        
        String: {<b> }
        Brace opens at 0, angle opens at 1, angle closes at 3.
        Brace [0,5] consumes the < marker. No closing > for angle outside brace.
        Expected: brace token {<b>, literal text space (and unpaired >)
        Actually: brace [0,5] = {<b> }, angle [1,3] is inside brace, < inside token, > inside token
        Brace is higher priority in this case.
        """
        result = lex_with_boundaries("{<b> }", [('{', '}'), ('<', '>')])
        expected = [Token(0, 0, ('{', '}'), "{<b> }")]
        self.assertEqual(result, expected)


class TestMacroEngine(unittest.TestCase):

    def setUp(self):
        # Initialize a blank engine for each test
        self.engine = PromptEngine("")

    def test_literal_text_passthrough(self):
        """Verify that literal text is returned unchanged."""
        prompt = "The quick brown fox jumps over the lazy dog"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, prompt)

    def test_simple_token_replacement(self):
        """Verify basic bounded token replacement."""
        self.engine._parse_global_context(":old:new")
        prompt = "This is <old> text"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, "This is new text")

    def test_multiple_definitions(self):
        """Verify multiple definitions can coexist and resolve correctly."""
        self.engine._parse_global_context(":color:blue\n:animal:dog")
        prompt = "A <color> <animal>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, "A blue dog")

    def test_strong_definition_overwrites_previous_strong(self):
        """Verify that a later strong definition shadows an earlier strong definition."""
        self.engine._parse_global_context(":color:blue\n:color:red")
        prompt = "The <color> car"
        result, trace = self.engine.generate(prompt)
        # Should use the most recent strong definition in left-to-right stack order
        self.assertEqual(result, "The red car")

    def test_weak_definition_does_not_overwrite_strong(self):
        """Verify that a weak definition does not override an earlier strong definition."""
        self.engine._parse_global_context(":color:blue\n:color::yellow")
        prompt = "The <color> car"
        result, trace = self.engine.generate(prompt)
        # Strong (blue) should win over weak (yellow)
        self.assertEqual(result, "The blue car")

    def test_weak_definition_acts_as_fallback(self):
        """Verify that a weak definition provides a fallback when no strong definition exists."""
        self.engine._parse_global_context(":color::yellow")
        prompt = "The <color> car"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, "The yellow car")

    def test_multiple_weak_definitions_first_wins(self):
        """Verify that among multiple weak definitions, the first inserted (oldest) is used when no strong exists."""
        self.engine._parse_global_context(":color::yellow\n:color::green")
        prompt = "The <color> car"
        result, trace = self.engine.generate(prompt)
        # Weak definitions are appended to tail; evaluation runs left-to-right, so yellow (older weak) is checked first
        self.assertEqual(result, "The yellow car")

    def test_escape_characters(self):
        """Verify that escaped syntax characters are treated as literals."""
        prompt = r"This is \<not a macro\>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, "This is <not a macro>")

    def test_recursive_evaluation(self):
        """Verify that key values containing other invocations are recursively evaluated."""
        self.engine._parse_global_context(":subject:the <color> car\n:color:red")
        prompt = "I see <subject>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, "I see the red car")

    def test_recursive_evaluation_order_independence(self):
        """Verify recursive evaluation works regardless of definition order."""
        # Define color before subject
        self.engine._parse_global_context(":color:blue\n:subject:the <color> car")
        prompt = "Look at <subject>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, "Look at the blue car")

    def test_regex_pattern(self):
        """Verify regex patterns in bounded tokens work correctly."""
        self.engine._parse_global_context(r":/cat/:feline")
        prompt = r"The black <cat>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, r"The black feline")

    def test_regex_pattern_with_capture(self):
        """Verify regex patterns with capture groups."""
        self.engine._parse_global_context(r":/(cat)/:/feline \\1/")
        prompt = r"The <cat>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, r"The feline cat")

    def test_regex_wildcard(self):
        """Verify regex in bounded definitions."""
        self.engine._parse_global_context(r":/^.*animal$/:creature")
        prompt = r"A <big animal>"
        result, trace = self.engine.generate(prompt)
        self.assertEqual(result, r"A creature")

    def test_escape_on_regex_pattern(self):
        """Verify escaped regex patterns are treated as literals."""
        self.engine._parse_global_context(r":\/cat\/:feline")
        prompt = r"The </cat/>"
        result, trace = self.engine.generate(prompt, debug=False)
        # This should be treated as a literal key '/cat/' rather than regex '/cat/'.
        self.assertEqual(result, r"The feline")

    # def test_escaped_colon_in_key_definition(self):
    #     """Verify that escaped colon in key is treated as literal key char."""
    #     self.engine._parse_global_context(r":foo\\:bar:baz")
    #     prompt = r"<foo:bar>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, r"baz")

    def test_escaped_slash_key_literal(self):
        """Verify that escaped leading slash avoids regex key mode and uses literal key."""
        self.engine._parse_global_context(r":\/cat\/:feline")
        prompt = r"</cat/>"
        result, trace = self.engine.generate(prompt, debug=False)
        self.assertEqual(result, r"feline")

    # COMMENTED OUT: Tests below are for future implementation
    # def test_strong_shadowing(self):
    #     """Verify that a local strong definition overrides a global definition."""
    #     self.engine._parse_global_context(":color:blue")
    #     # Pseudo-syntax: invoking <subject> with a local override for color
    #     prompt = "<subject|color:red>" 
    #     result, trace = self.engine.generate(prompt)
    #     
    #     # If <subject> evaluates to "The <color> car"
    #     # The output must be "The red car", not blue.
    #     self.assertEqual(trace.get("subject_inner_resolution"), "The red car")
    #
    # def test_weak_defaults(self):
    #     """Verify that weak definitions act as fallbacks but are overridden by globals."""
    #     self.engine._parse_global_context(":color:green")
    #     # Local weak default ::color:yellow should be defeated by global strong :color:green
    #     prompt = "<subject|color::yellow>"
    #     result, trace = self.engine.generate(prompt)
    #     
    #     self.assertEqual(trace.get("subject_inner_resolution"), "The green car")
    #
    # def test_lexical_scoping_isolation(self):
    #     """Verify that arguments passed to Node A do not leak to sibling Node B."""
    #     self.engine._parse_global_context(":man:gentleman")
    #     # <A> gets arg, <B> does not.
    #     prompt = "<A|man:knight> and <B>"
    #     result, trace = self.engine.generate(prompt)
    #     
    #     self.assertIn("knight", trace.get("A"))
    #     self.assertIn("gentleman", trace.get("B"))
    #
    # def test_transparent_dummy_root(self):
    #     """Verify the < | > syntax allows sibling scope sharing."""
    #     prompt = "< | <A|man:king> | <B> >"
    #     result, trace = self.engine.generate(prompt)
    #     
    #     # Because A was transparently evaluated in the dummy root, 
    #     # its strong definition 'man:king' leaked to the dummy root scope, affecting B.
    #     self.assertIn("king", trace.get("A"))
    #     self.assertIn("king", trace.get("B"))
    #
    # def test_unbounded_execution_order(self):
    #     """Verify Pre and Post patterns execute in correct Right-to-Left definition priority."""
    #     self.engine._parse_global_context(":< /cat/ : feline\n:< /black cat/ : panther")
    #     prompt = "A black cat"
    #     result, trace = self.engine.generate(prompt)
    #     
    #     # If Weak (feline) executed before Strong (panther), output would be "black feline".
    #     # Correct execution yields "A panther".
    #     self.assertEqual(result.strip(), "A panther")

if __name__ == '__main__':
    unittest.main()