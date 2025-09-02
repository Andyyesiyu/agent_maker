import unittest
from agent_maker.core.state import Plan, ConversationState


class TestPlan(unittest.TestCase):
    def test_add_and_mark(self):
        plan = Plan()
        item = plan.add("task1", _id="123")
        self.assertEqual(item.status, "pending")
        self.assertTrue(plan.mark("123", "done"))
        self.assertEqual(plan.items[0].status, "done")


class TestConversationState(unittest.TestCase):
    def test_history(self):
        state = ConversationState()
        state.add_message("user", "hello")
        self.assertEqual(state.to_history(), [{"role": "user", "content": "hello"}])


if __name__ == "__main__":
    unittest.main()
