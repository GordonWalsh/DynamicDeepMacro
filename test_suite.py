import unittest
from macro_engine import PromptEngine, MacroContext, Definition

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
        self.engine._parse_global_context(r":\\/cat\\/:feline")
        prompt = r"The </cat/>"
        result, trace = self.engine.generate(prompt)
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
        self.engine._parse_global_context(r":\\/cat\\/:feline")
        prompt = r"</cat/>"
        result, trace = self.engine.generate(prompt)
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