from typing import List, Tuple
import unittest
from core_types import Token, TokenType
from lexer import lex
# Optional depending on implementation: from config import SyntaxConfig

def wrap_tokens(items: List[Tuple[str,TokenType]] = None):
    """
    Convert list of strings and TokenTypes to list of Tokens for test comparison.
    
    Allows test expectations to be written more clearly while comparing
    against Token objects. Will assume TokenType.LITERAL for all unprovided types.
    
    Args:
        items: List of (string, TokenType) Tuples to convert to Tokens
    
    Returns:
        List of Token objects, with strings converted to typed tokens
    """
    result = []
    for item in items:
        result.append(Token(value=item[0], position=0, length=0, token_type=(item[1] if item[1] else TokenType.LITERAL)))
    return result


class TestLexer(unittest.TestCase):
    """Test suite for the lex() tokenizer function."""

    def test_literal_text_only(self):
        """Verify that plain text with no boundaries is returned as a single element."""
        result = lex(r'hello world')
        self.assertEqual(result, wrap_tokens([(r'hello world', TokenType.LITERAL)]))

    def test_single_bounded_token(self):
        """Verify basic bounded token detection with single boundary type."""
        result = lex(r'hello <world>')
        expected = wrap_tokens([(r'hello ', TokenType.LITERAL), (r'<world>', TokenType.INVOCATION)])
        self.assertEqual(result, expected)

    def test_multiple_bounded_tokens_same_type(self):
        """Verify multiple tokens of the same boundary type."""
        result = lex(r'The <color> <animal> ran')
        expected = wrap_tokens([(r'The ', TokenType.LITERAL), (r'<color>', TokenType.INVOCATION), (r' ', TokenType.LITERAL), (r'<animal>', TokenType.INVOCATION), (r' ran', TokenType.LITERAL)])
        self.assertEqual(result, expected)

    def test_multiple_boundary_types(self):
        """Verify handling of multiple boundary types."""
        result = lex(r'hello <world> and {test} end')
        expected = wrap_tokens([(r'hello ', TokenType.LITERAL), (r'<world>', TokenType.INVOCATION), (r' and ', TokenType.LITERAL), (r'{test}', TokenType.GROUP), (r' end', TokenType.LITERAL)])
        self.assertEqual(result, expected)

    def test_boundary_at_string_start(self):
        """Verify token at the start of the string."""
        result = lex(r'<start> of text')
        expected = wrap_tokens([(r'<start>', TokenType.INVOCATION), (r' of text', TokenType.LITERAL)])
        self.assertEqual(result, expected)

    def test_boundary_at_string_end(self):
        """Verify token at the end of the string."""
        result = lex(r'end of <text>')
        expected = wrap_tokens([(r'end of ', TokenType.LITERAL), (r'<text>', TokenType.INVOCATION)])
        self.assertEqual(result, expected)

    def test_consecutive_boundaries(self):
        """Verify consecutive tokens with no literal text between them."""
        result = lex(r'<first><second>')
        expected = wrap_tokens([(r'<first>', TokenType.INVOCATION), (r'<second>', TokenType.INVOCATION)])
        self.assertEqual(result, expected)

    def test_nested_boundaries_same_type(self):
        """Verify that nested boundaries of the same type are kept as flat content."""
        result = lex(r'text <outer <inner> content>')
        # <inner> should be treated as literal content, not a separate token
        expected = wrap_tokens([(r'text ', TokenType.LITERAL), (r'<outer <inner> content>', TokenType.INVOCATION)])
        self.assertEqual(result, expected)

    def test_nested_boundaries_different_types(self):
        """Verify that mixed nested boundaries are preserved as flat content."""
        result = lex(r'a <outer {inner} content>')
        # {inner} should not trigger a split; it's nested inside <>
        expected = wrap_tokens([(r'a ', TokenType.LITERAL), (r'<outer {inner} content>', TokenType.INVOCATION)])
        self.assertEqual(result, expected)

    def test_empty_boundary(self):
        """Verify that empty boundaries are kept as valid tokens."""
        result = lex(r'text <> more')
        expected = wrap_tokens([(r'text ', TokenType.LITERAL), (r'<>', TokenType.INVOCATION), (r' more', TokenType.LITERAL)])
        self.assertEqual(result, expected)

    def test_unclosed_boundary_end_of_string(self):
        """Verify that unclosed boundary at end of string is treated as literal."""
        result = lex(r'text unclosed<')
        self.assertEqual(result, wrap_tokens([(r'text unclosed<', TokenType.LITERAL)]))

    def test_unclosed_boundary_with_following_text(self):
        """Verify that unclosed boundary with following text is emitted as literal."""
        result = lex(r'text <unclosed more')
        self.assertEqual(result, wrap_tokens([(r'text <unclosed more', TokenType.LITERAL)]))

    def test_extra_closing_marker(self):
        """Verify that extra closing markers are treated as literal text."""
        result = lex(r'text > unmatched')
        self.assertEqual(result, wrap_tokens([(r'text > unmatched', TokenType.LITERAL)]))

    def test_escape_opening_marker(self):
        """Verify that escaped opening marker is treated as literal."""
        result = lex(r"text \<not a token\>")
        self.assertEqual(result, wrap_tokens([(r"text \<not a token\>", TokenType.LITERAL)]))

    def test_escape_closing_marker(self):
        """Verify that escaped closing marker inside token prevents token closure."""
        result = lex(r"text <content\> still inside>")
        expected = wrap_tokens([(r'text ', TokenType.LITERAL), (r"<content\> still inside>", TokenType.INVOCATION)])
        self.assertEqual(result, expected)

    def test_escape_backslash(self):
        """Verify that escaped backslash is treated as literal."""
        result = lex(r"text \\ not escaped")
        self.assertEqual(result, wrap_tokens([(r"text \\ not escaped", TokenType.LITERAL)]))

    def test_backslash_before_non_syntax_char(self):
        """Verify that backslash before non-syntax character is kept as-is."""
        result = lex(r"text \a literal")
        self.assertEqual(result, wrap_tokens([(r"text \a literal", TokenType.LITERAL)]))

    def test_default_boundaries(self):
        """Verify that default boundaries are { } and < > with { } priority."""
        result = lex(r'a <b> c {d} e')
        expected = wrap_tokens([(r'a ', TokenType.LITERAL), (r'<b>', TokenType.INVOCATION), (r' c ', TokenType.LITERAL), (r'{d}', TokenType.GROUP), (r' e', TokenType.LITERAL)])
        self.assertEqual(result, expected)

    def test_multiple_unclosed_at_end(self):
        """Verify multiple unclosed boundaries are emitted together as literal."""
        result = lex(r'text <unclosed {also')
        self.assertEqual(result, wrap_tokens([(r'text <unclosed {also', TokenType.LITERAL)]))

    def test_interleaved_brace_consumes_angle(self):
        """Verify interleaved boundaries with brace priority.
        
        String: <a {b> }
        With brace priority, brace [3,7] consumes the < marker.
        Angle < is outside brace token (at 0), > is inside → < becomes literal.
        Expected: literal text <a , brace token {b> }
        """
        result = lex(r'<a {b> }')
        expected = wrap_tokens([(r'<a ', TokenType.LITERAL), (r'{b> }', TokenType.GROUP)])
        self.assertEqual(result, expected)

    def test_interleaved_brace_before_angle(self):
        """Verify interleaved boundaries where brace opens first.
        
        String: {<b> }
        Brace opens at 0, angle opens at 1, angle closes at 3.
        Brace [0,5] consumes the < marker. No closing > for angle outside brace.
        Expected: brace token {<b>, literal text space (and unpaired >)
        Actually: brace [0,5] = {<b> }, angle [1,3] is inside brace, < inside token, > inside token
        Brace is higher priority in this case.
        """
        result = lex(r'{<b> }')
        expected = wrap_tokens([(r'{<b> }', TokenType.GROUP)])
        self.assertEqual(result, expected)

class TestDiscreteTokens(unittest.TestCase):
    """Test suite for discrete (unpaired) zero-depth markers like | and $$."""

    def test_zero_depth_split(self):
        """Verify | is detected at the top level."""
        result = lex(r'A | B | C')
        expected = wrap_tokens([
            (r'A ', TokenType.LITERAL),
            (r'|', TokenType.SPLIT),
            (r' B ', TokenType.LITERAL),
            (r'|', TokenType.SPLIT),
            (r' C', TokenType.LITERAL)
        ])
        self.assertEqual(result, expected)

    def test_discrete_culling_inside_boundaries(self):
        """Verify discrete markers are neutralized when inside higher-order boundaries."""
        # Split inside Invocation
        result1 = lex(r'<foo | bar>')
        self.assertEqual(result1, wrap_tokens([(r'<foo | bar>', TokenType.INVOCATION)]))

        # Split inside Group
        result2 = lex(r'{a | b}')
        self.assertEqual(result2, wrap_tokens([(r'{a | b}', TokenType.GROUP)]))
        
        # Modifier inside Group
        result3 = lex(r'{2$$foo}')
        self.assertEqual(result3, wrap_tokens([(r'{2$$foo}', TokenType.GROUP)]))

    def test_zero_depth_modifier(self):
        """Verify $$ is detected correctly at the top level."""
        result = lex(r'2$$<key>')
        expected = wrap_tokens([
            (r'2', TokenType.LITERAL),
            (r'$$', TokenType.MODIFIER),
            (r'<key>', TokenType.INVOCATION)
        ])
        self.assertEqual(result, expected)

    def test_escaped_discrete_markers(self):
        """Verify (single) \\| prevents split tokenization."""
        result = lex(r'a \| b')
        self.assertEqual(result, wrap_tokens([(r'a \| b', TokenType.LITERAL)]))

class TestDefinitionTokens(unittest.TestCase):
    """Test suite for Definition tokens, including EOL and Multi-line Blocks."""

    def test_eol_definition(self):
        """Verify standard definitions terminate at the newline."""
        result = lex(":key:value\nNext line")
        expected = wrap_tokens([
            (":key:value", TokenType.DEFINITION),
            ("\nNext line", TokenType.LITERAL)
        ])
        self.assertEqual(result, expected)

    def test_multi_line_block_definition(self):
        """Verify << >> wraps multiple lines and ignores EOL."""
        text = ":key:<<\nLine 1\nLine 2\n>>\nTrailing"
        result = lex(text)
        expected = wrap_tokens([
            (":key:<<\nLine 1\nLine 2\n>>", TokenType.DEFINITION),
            ("\nTrailing", TokenType.LITERAL)
        ])
        self.assertEqual(result, expected)

    def test_nested_blocks_inside_definition(self):
        """Verify the pushdown automaton tracks nested << >>."""
        text = ":outer:<<\n:inner:<<\nnested\n>>\n>>"
        result = lex(text)
        self.assertEqual(result, wrap_tokens([(text, TokenType.DEFINITION)]))

    def test_definition_culling(self):
        """Verify definitions are neutralized if inside a higher boundary."""
        # EOL def inside an Invocation
        result1 = lex("<foo :key:val>")
        self.assertEqual(result1, wrap_tokens([("<foo :key:val>", TokenType.INVOCATION)]))
        
        # Block def inside a Group
        result2 = lex("{ :key:<<val>> }")
        self.assertEqual(result2, wrap_tokens([("{ :key:<<val>> }", TokenType.GROUP)]))

    def test_inline_colon_ignored(self):
        """Verify standard text colons do not trigger definitions."""
        result = lex("Time: 12:00")
        self.assertEqual(result, wrap_tokens([("Time: 12:00", TokenType.LITERAL)]))

# class TestMacroEngine(unittest.TestCase):
    # def setUp(self):
    #     # Initialize a blank engine for each test
    #     self.engine = PromptEngine("")

    # def test_literal_text_passthrough(self):
    #     """Verify that literal text is returned unchanged."""
    #     prompt = "The quick brown fox jumps over the lazy dog"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, prompt)

    # def test_simple_token_replacement(self):
    #     """Verify basic bounded token replacement."""
    #     self.engine._parse_global_context(":old:new")
    #     prompt = "This is <old> text"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, "This is new text")

    # def test_multiple_definitions(self):
    #     """Verify multiple definitions can coexist and resolve correctly."""
    #     self.engine._parse_global_context(":color:blue\n:animal:dog")
    #     prompt = "A <color> <animal>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, "A blue dog")

    # def test_strong_definition_overwrites_previous_strong(self):
    #     """Verify that a later strong definition shadows an earlier strong definition."""
    #     self.engine._parse_global_context(":color:blue\n:color:red")
    #     prompt = "The <color> car"
    #     result, trace = self.engine.generate(prompt)
    #     # Should use the most recent strong definition in left-to-right stack order
    #     self.assertEqual(result, "The red car")

    # def test_weak_definition_does_not_overwrite_strong(self):
    #     """Verify that a weak definition does not override an earlier strong definition."""
    #     self.engine._parse_global_context(":color:blue\n:color::yellow")
    #     prompt = "The <color> car"
    #     result, trace = self.engine.generate(prompt)
    #     # Strong (blue) should win over weak (yellow)
    #     self.assertEqual(result, "The blue car")

    # def test_weak_definition_acts_as_fallback(self):
    #     """Verify that a weak definition provides a fallback when no strong definition exists."""
    #     self.engine._parse_global_context(":color::yellow")
    #     prompt = "The <color> car"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, "The yellow car")

    # def test_multiple_weak_definitions_first_wins(self):
    #     """Verify that among multiple weak definitions, the first inserted (oldest) is used when no strong exists."""
    #     self.engine._parse_global_context(":color::yellow\n:color::green")
    #     prompt = "The <color> car"
    #     result, trace = self.engine.generate(prompt)
    #     # Weak definitions are appended to tail; evaluation runs left-to-right, so yellow (older weak) is checked first
    #     self.assertEqual(result, "The yellow car")

    # def test_escape_characters(self):
    #     """Verify that escaped syntax characters are treated as literals."""
    #     prompt = r"This is \<not a macro\>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, "This is <not a macro>")

    # def test_recursive_evaluation(self):
    #     """Verify that key values containing other invocations are recursively evaluated."""
    #     self.engine._parse_global_context(":subject:the <color> car\n:color:red")
    #     prompt = "I see <subject>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, "I see the red car")

    # def test_recursive_evaluation_order_independence(self):
    #     """Verify recursive evaluation works regardless of definition order."""
    #     # Define color before subject
    #     self.engine._parse_global_context(":color:blue\n:subject:the <color> car")
    #     prompt = "Look at <subject>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, "Look at the blue car")

    # def test_regex_pattern(self):
    #     """Verify regex patterns in bounded tokens work correctly."""
    #     self.engine._parse_global_context(r":/cat/:feline")
    #     prompt = r"The black <cat>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, r"The black feline")

    # def test_regex_pattern_with_capture(self):
    #     """Verify regex patterns with capture groups."""
    #     self.engine._parse_global_context(r":/(cat)/:/feline \\1/")
    #     prompt = r"The <cat>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, r"The feline cat")

    # def test_regex_wildcard(self):
    #     """Verify regex in bounded definitions."""
    #     self.engine._parse_global_context(r":/^.*animal$/:creature")
    #     prompt = r"A <big animal>"
    #     result, trace = self.engine.generate(prompt)
    #     self.assertEqual(result, r"A creature")

    # def test_escape_on_regex_pattern(self):
    #     """Verify escaped regex patterns are treated as literals."""
    #     self.engine._parse_global_context(r":\/cat\/:feline")
    #     prompt = r"The </cat/>"
    #     result, trace = self.engine.generate(prompt, debug=False)
    #     # This should be treated as a literal key '/cat/' rather than regex '/cat/'.
    #     self.assertEqual(result, r"The feline")

    # # def test_escaped_colon_in_key_definition(self):
    # #     """Verify that escaped colon in key is treated as literal key char."""
    # #     self.engine._parse_global_context(r":foo\\:bar:baz")
    # #     prompt = r"<foo:bar>"
    # #     result, trace = self.engine.generate(prompt)
    # #     self.assertEqual(result, r"baz")

    # def test_escaped_slash_key_literal(self):
    #     """Verify that escaped leading slash avoids regex key mode and uses literal key."""
    #     self.engine._parse_global_context(r":\/cat\/:feline")
    #     prompt = r"</cat/>"
    #     result, trace = self.engine.generate(prompt, debug=False)
    #     self.assertEqual(result, r"feline")

    # # COMMENTED OUT: Tests below are for future implementation
    # # def test_strong_shadowing(self):
    # #     """Verify that a local strong definition overrides a global definition."""
    # #     self.engine._parse_global_context(":color:blue")
    # #     # Pseudo-syntax: invoking <subject> with a local override for color
    # #     prompt = "<subject|color:red>" 
    # #     result, trace = self.engine.generate(prompt)
    # #     
    # #     # If <subject> evaluates to "The <color> car"
    # #     # The output must be "The red car", not blue.
    # #     self.assertEqual(trace.get("subject_inner_resolution"), "The red car")
    # #
    # # def test_weak_defaults(self):
    # #     """Verify that weak definitions act as fallbacks but are overridden by globals."""
    # #     self.engine._parse_global_context(":color:green")
    # #     # Local weak default ::color:yellow should be defeated by global strong :color:green
    # #     prompt = "<subject|color::yellow>"
    # #     result, trace = self.engine.generate(prompt)
    # #     
    # #     self.assertEqual(trace.get("subject_inner_resolution"), "The green car")
    # #
    # # def test_lexical_scoping_isolation(self):
    # #     """Verify that arguments passed to Node A do not leak to sibling Node B."""
    # #     self.engine._parse_global_context(":man:gentleman")
    # #     # <A> gets arg, <B> does not.
    # #     prompt = "<A|man:knight> and <B>"
    # #     result, trace = self.engine.generate(prompt)
    # #     
    # #     self.assertIn("knight", trace.get("A"))
    # #     self.assertIn("gentleman", trace.get("B"))
    # #
    # # def test_transparent_dummy_root(self):
    # #     """Verify the < | > syntax allows sibling scope sharing."""
    # #     prompt = "< | <A|man:king> | <B> >"
    # #     result, trace = self.engine.generate(prompt)
    # #     
    # #     # Because A was transparently evaluated in the dummy root, 
    # #     # its strong definition 'man:king' leaked to the dummy root scope, affecting B.
    # #     self.assertIn("king", trace.get("A"))
    # #     self.assertIn("king", trace.get("B"))
    # #
    # # def test_unbounded_execution_order(self):
    # #     """Verify Pre and Post patterns execute in correct Right-to-Left definition priority."""
    # #     self.engine._parse_global_context(":< /cat/ : feline\n:< /black cat/ : panther")
    # #     prompt = "A black cat"
    # #     result, trace = self.engine.generate(prompt)
    # #     
    # #     # If Weak (feline) executed before Strong (panther), output would be "black feline".
    # #     # Correct execution yields "A panther".
    # #     self.assertEqual(result.strip(), "A panther")

if __name__ == '__main__':
    unittest.main()