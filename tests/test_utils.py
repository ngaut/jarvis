# test_utils.py

import unittest
from unittest.mock import patch
from smartgpt.utils import eval_expression

class TestUtils(unittest.TestCase):
    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_single(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_multiple(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}, {"key":"@eval("key_features_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected_1 = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}, {"key":"key_features_0.seq3.list", "value":"<to_fill>"}]}'
        expected_2 = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}, {"key":"key_features_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(eval_expression(text), expected_1)
        self.assertEqual(eval_expression(expected_1), expected_2)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_eval_expression_nested(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq"+ str(jvm.get("idx") + 3) + ".list")", "value":"<to_fill>"}]}'
        expected = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_incorrect_parentheses(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list"", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_non_existent_variable(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(non_existent_variable) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_syntax_error(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + strjvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_incomplete_string(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx") + ".seq3.list", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_invalid_operation(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx"))/0 + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_missing_closing_tag(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list", "value":"<to_fill>"}]}'
        expected = None
        self.assertEqual(eval_expression(text), expected)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_multiple_evals(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list") + @eval("_extra")", "value":"<to_fill>"}]}'
        expected_1 = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list") + _extra", "value":"<to_fill>"}]}'
        expected_2 = '{"kvs":[{"key":"key_points_0.seq3.list + _extra", "value":"<to_fill>"}]}'
        self.assertEqual(eval_expression(text), expected_1)
        self.assertEqual(eval_expression(expected_1), expected_2)

    @patch('smartgpt.jvm.get', return_value=0)
    def test_nested_evals(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + "@eval(str(jvm.get("idx")))" + ".seq3.list")", "value":"<to_fill>"}]}'
        expected_1 = '{"kvs":[{"key":"@eval("key_points_" + "0" + ".seq3.list")", "value":"<to_fill>"}]}'
        expected_2 = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(eval_expression(text), expected_1)
        self.assertEqual(eval_expression(expected_1), expected_2)

    @patch('smartgpt.jvm.get', return_value=1)
    def test_eval_with_different_mock_value(self, mock_get):
        text = '{"kvs":[{"key":"@eval("key_points_" + str(jvm.get("idx")) + ".seq3.list")", "value":"<to_fill>"}]}'
        expected = '{"kvs":[{"key":"key_points_1.seq3.list", "value":"<to_fill>"}]}'
        self.assertEqual(eval_expression(text), expected)

if __name__ == "__main__":
    unittest.main()
