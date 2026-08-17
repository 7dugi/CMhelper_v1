import unittest
from automation.state_machine import StateMachine
from automation.models import TaskState

class TestH3Fixes(unittest.TestCase):
    def test_reviewing_to_revising_valid(self):
        sm = StateMachine(TaskState.REVIEWING)
        sm.transition(TaskState.REVISING)
        self.assertEqual(sm.current_state, TaskState.REVISING)

    def test_revising_to_implementing_valid(self):
        sm = StateMachine(TaskState.REVISING)
        sm.transition(TaskState.IMPLEMENTING)
        self.assertEqual(sm.current_state, TaskState.IMPLEMENTING)

    def test_reviewing_to_implementing_rejected(self):
        sm = StateMachine(TaskState.REVIEWING)
        with self.assertRaises(ValueError):
            sm.transition(TaskState.IMPLEMENTING)

if __name__ == '__main__':
    unittest.main()
