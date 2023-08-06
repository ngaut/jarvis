# test_utils.py

import unittest
from unittest.mock import patch

from jarvis.smartgpt import jvm

class TestUtils(unittest.TestCase):
    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_single(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_multiple(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}, {"key":"jvm.eval("key_features_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected_1 = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}, {"key":"key_features_0.seq3.list", "value":"<to_fill>"}]}'
        expected_2 = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}, {"key":"key_features_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(jvm.eval(text), expected_1)
        self.assertEqual(jvm.eval(expected_1), expected_2)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_nested(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq"+ str(jvm.get("idx") + 3) + ".list")", "value":"<to_fill>"}]}'
        expected = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_incorrect_parentheses(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list"", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_non_existent_variable(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(non_existent_variable) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_syntax_error(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + strjvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_incomplete_string(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx") + ".seq3.list", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_invalid_operation(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx"))/0 + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_missing_closing_tag(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_multiple_evals(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list") + jvm.eval("_extra")", "value":"<to_fill>"}]}'
        expected_1 = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list") + _extra", "value":"<to_fill>"}]}'
        expected_2 = '{"kvs":[{"key":"key_points_0.seq3.list + _extra", "value":"<to_fill>"}]}'
        self.assertEqual(jvm.eval(text), expected_1)
        self.assertEqual(jvm.eval(expected_1), expected_2)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_nested_evals(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + "jvm.eval(str(jvm.get("idx")))" + ".seq3.list")", "value":"<to_fill>"}]}'
        expected_1 = '{"kvs":[{"key":"jvm.eval("key_points_" + "0" + ".seq3.list")", "value":"<to_fill>"}]}'
        expected_2 = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(jvm.eval(text), expected_1)
        self.assertEqual(jvm.eval(expected_1), expected_2)

    @patch('smartgpt.jvm.get', return_value=1)
    def test_eval_with_different_mock_value(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = '{"kvs":[{"key":"key_points_1.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=1)
    def test_eval_without_eval(self, mock_get):
        text = '{"kvs":[{"key":"key_points_" + str(jvm.get("idx")) + ".seq3.list", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(jvm.eval(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_multiple_nested_evals(self, mock_get):
        text = 'jvm.eval("key_points_" + "jvm.eval(str(jvm.get("jvm.eval("idx")")))" + ".seqjvm.eval(str(1+1+1)).list")'
        expected = 'key_points_0.seq3.list'
        result = jvm.eval(text)
        result = jvm.eval(result)
        result = jvm.eval(result)
        result = jvm.eval(result)
        self.assertEqual(result, expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_complex(self, mock_get):
        text = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq"+ str(jvm.eval(jvm.eval("2*" + str(jvm.get("idx"))))) + ".list")", "value":"<to_fill>"}]}'
        expected_step_1 = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq"+ str(jvm.eval(2*0)) + ".list")", "value":"<to_fill>"}]}'
        expected_step_2 = '{"kvs":[{"key":"jvm.eval("key_points_" + str(jvm.get("idx")) + ".seq"+ str(0) + ".list")", "value":"<to_fill>"}]}'
        expected_step_3 = '{"kvs":[{"key":"key_points_0.seq0.list", "value":"<to_fill>"}]}'

        self.assertEqual(jvm.eval(text), expected_step_1)
        self.assertEqual(jvm.eval(expected_step_1), expected_step_2)
        self.assertEqual(jvm.eval(expected_step_2), expected_step_3)


if __name__ == "__main__":
    unittest.main()
