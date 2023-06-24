import unittest
from unittest import mock
from smartgpt.instruction import JVMInstruction

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
        # TODO: Add setup for this test case
        # TODO: Run test case
        # TODO: Assert expected outcome
        pass

    def test_eval_and_patch_multiple_key_value_pairs(self):
        text_input = "{'kvs':[{'key': '@eval(jvm.get(\"key1\"))', 'value': 'value1'}, {'key': '@eval(jvm.get(\"key2\"))', 'value': 'value2'}]}"
        expected_output = '{"kvs":[{"key": "new_key2", "value": "value1"}, {"key": "new_key1", "value": "value2"}]}'

        # Assuming jvm.get("key1") returns "new_key1" and jvm.get("key2") returns "new_key2"
        # Considering that @eval() is in a right-to-left order, expected_output needs to pay attention to this
        # Here we should use mock.patch to simulate the behavior of jvm.get
        with mock.patch('smartgpt.instruction.jvm.get', side_effect=['new_key1', 'new_key2']):
            actual_output = self.instruction.eval_and_patch(text_input)

        self.assertEqual(actual_output, expected_output)

    # Add more test cases for eval_and_patch ...

    def test_post_exec_no_brackets(self):
        # TODO: Add setup for this test case
        # TODO: Run test case
        # TODO: Assert expected outcome
        pass

    def test_post_exec_invalid_json(self):
        # TODO: Add setup for this test case
        # TODO: Run test case
        # TODO: Assert expected outcome
        pass

    # Add more test cases for post_exec ...

if __name__ == "__main__":
    unittest.main()
