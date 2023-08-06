import unittest
from unittest import mock
import json

from jarvis.smartgpt.instruction import JVMInstruction

class TestInstruction(unittest.TestCase):
    def setUp(self):
        self.instruction = JVMInstruction(None, None, None)

    def test_eval_and_patch_1(self):
        text_input = "{'kvs':[{'key':\"key_points_\" + str(jvm.get(\"idx\")) + \".seq3.list\", 'value':'<to_fill>'}, {'key':'features_' + str(jvm.get('idx')) + '.seq3.list', 'value':'<to_fill>'}]}"
        expected_output = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}, {"key":"features_0.seq3.list", "value":"<to_fill>"}]}'

        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', return_value=0):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_2(self):
        text_input = '{"kvs":[{"key":"key_points_" + str(jvm.get(\'idx\')) + ".seq3.list", "value":"<to_fill>"}, {"key":"features_" + str(jvm.get(\'idx\')) + ".seq3.list", "value":"<to_fill>"}]}'
        expected_output = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}, {"key":"features_0.seq3.list", "value":"<to_fill>"}]}'

        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', return_value=0):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_no_kvs(self):
        # Test case where 'kvs' is not in the input text
        text_input = '{"some_other_key":[{"key":"key1", "value":"value1"}, {"key":"key2", "value":"value2"}]}'
        expected_output = text_input  # Expected output is the same as input because 'kvs' is not found

        actual_output = self.instruction.eval_and_patch(text_input)
        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_multiple_key_value_pairs(self):
        text_input = "{'kvs':[{'key': 'jvm.eval(jvm.get(\"key1\"))', 'value': 'value1'}, {'key': 'jvm.eval(jvm.get(\"key2\"))', 'value': 'value2'}]}"
        expected_output = '{"kvs":[{"key": "new_key2", "value": "value1"}, {"key": "new_key1", "value": "value2"}]}'

        # Assuming jvm.get("key1") returns "new_key1" and jvm.get("key2") returns "new_key2"
        # Considering that jvm.eval() is in a right-to-left order, expected_output needs to pay attention to this
        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', side_effect=['new_key1', 'new_key2']):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_empty_kvs(self):
        # Test case where 'kvs' exists but has no key-value pairs
        text_input = '{"kvs":[]}'
        expected_output = text_input  # Expected output is the same as input because there are no key-value pairs

        actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_non_string_key(self):
        # Test case where 'key' in 'kvs' is not a string
        text_input = '{"kvs":[{"key":123, "value":"value1"}]}'
        expected_output = text_input  # Expected output is the same as input because 'key' is not a string

        actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_no_key_in_kvs(self):
        # Test case where 'key' is not in 'kvs'
        text_input = '{"kvs":[{"value":"value1"}]}'
        expected_output = text_input  # Expected output is the same as input because 'key' is not in 'kvs'

        actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_no_value_in_kvs(self):
        # Test case where 'value' is not in 'kvs'
        text_input = '{"kvs":[{"key":"key1"}]}'
        expected_output = text_input  # Expected output is the same as input because 'value' is not in 'kvs'

        actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_mixed_string_delimiters(self):
        # Test case where string delimiters are mixed
        text_input = "{'kvs':[{'key':\"key_points_\" + str(jvm.get(\"idx\")) + \".seq3.list\", 'value':'<to_fill>'}, {'key':'features_' + str(jvm.get('idx')) + '.seq3.list', 'value':'<to_fill>'}]}"
        expected_output = '{"kvs":[{"key":"key_points_0.seq3.list", "value":"<to_fill>"}, {"key":"features_0.seq3.list", "value":"<to_fill>"}]}'

        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', return_value=0):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_complex_expression_single_quotes(self):
        # Test case where the key expression involves complex operations
        text_input = "{'kvs':[{'key':'jvm.eval(\"key_points_\" + str(jvm.get(\"idx\")) + \"_\" + str(jvm.get(\"id\")) + \".seq3.list\")', 'value':'<to_fill>'}, {'key':\"features_\" + str(jvm.get(\"id\")) + \"_\" + str(jvm.get(\"idx\")) + \".seq3.list\", 'value':'<to_fill>'}]}"
        expected_output = '{"kvs":[{"key":"key_points_0_1.seq3.list", "value":"<to_fill>"}, {"key":"features_1_0.seq3.list", "value":"<to_fill>"}]}'

        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', side_effect=[0, 1, 1, 0]):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_complex_expression_double_quotes(self):
        # Test case where the key expression involves complex operations
        text_input = '{"kvs":[{"key":"jvm.eval(\'key_points_\' + str(jvm.get(\'idx\')) + \'_\' + str(jvm.get(\'id\')) + \'.seq3.list\')", "value":"<to_fill>"}, {"key":\'features_\' + str(jvm.get(\'id\')) + \'_\' + str(jvm.get(\'idx\')) + \'.seq3.list\', "value":"<to_fill>"}]}'
        expected_output = '{"kvs":[{"key":"key_points_0_1.seq3.list", "value":"<to_fill>"}, {"key":"features_1_0.seq3.list", "value":"<to_fill>"}]}'

        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', side_effect=[0, 1, 1, 0]):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_eval_and_patch_get_condition_key(self):
        text_input = 'jvm.eval(jvm.get("weather_notes.seq5.str") or jvm.get("weather_notes.seq6.str"))'
        expected_output = "the weather is sunny and warm (from weather_notes.seq6.str)"

        # Assuming jvm.get("key1") returns None and jvm.get("key2") returns "the weather is sunny and warm"
        # Considering that jvm.eval() is in a right-to-left order, expected_output needs to pay attention to this
        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', side_effect=["the weather is sunny and warm (from weather_notes.seq6.str)", None]):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

        expected_output = "the weather is cloudy and cold (from weather_notes.seq5.str)"
        with mock.patch('smartgpt.instruction.jvm.get', side_effect=[None, "the weather is cloudy and cold (from weather_notes.seq5.str)"]):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    def test_post_exec_valid_json(self):
        result = '{"kvs":[{"key": "key1", "value": "value1"}, {"key": "key2", "value": "value2"}]}'
        expected_calls = [mock.call("key1", "value1"), mock.call("key2", "value2")]

        with mock.patch('smartgpt.instruction.jvm.set') as mock_set:
            self.instruction.post_exec(result)

        mock_set.assert_has_calls(expected_calls, any_order=True)

    def test_post_exec_invalid_json(self):
        result = 'Invalid JSON string'

        with mock.patch('smartgpt.instruction.jvm.set') as mock_set:
            self.instruction.post_exec(result)

        mock_set.assert_not_called()

    def test_post_exec_no_kvs(self):
        result = '{"no_kvs": []}'

        with mock.patch('smartgpt.instruction.jvm.set') as mock_set:
            self.instruction.post_exec(result)

        mock_set.assert_not_called()

    def test_post_exec_malformed_kvs(self):
        result = '{"kvs":[{"key": "key1", "value": "value1"}, {"malformed": true}]}'
        expected_calls = [mock.call("key1", "value1")]

        with mock.patch('smartgpt.instruction.jvm.set') as mock_set:
            self.instruction.post_exec(result)

        mock_set.assert_has_calls(expected_calls, any_order=True)

    def test_post_exec_fetch_result(self):
        result = {"kvs": [{"key": "search_content_seq0.str", "value": "the quick brown fox jumps over the lazy dog"}]}
        result_json_str = json.dumps(result)
        expected_calls = [mock.call("search_content_seq0.str", "the quick brown fox jumps over the lazy dog")]

        with mock.patch('smartgpt.instruction.jvm.set') as mock_set:
            self.instruction.post_exec(result_json_str)

        mock_set.assert_has_calls(expected_calls, any_order=True)

    def test_post_exec_websearch_result(self):
        result = {"kvs": [{"key": "search_url_seq0.list", "value": ["https://wwww.google.com", "https://www.apple.com"]}]}
        result_json_str = json.dumps(result)
        expected_calls = [mock.call("search_url_seq0.list", ["https://wwww.google.com", "https://www.apple.com"])]

        with mock.patch('smartgpt.instruction.jvm.set') as mock_set:
            self.instruction.post_exec(result_json_str)

        mock_set.assert_has_calls(expected_calls, any_order=True)

if __name__ == "__main__":
    unittest.main()
