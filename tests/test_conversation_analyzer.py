import unittest
from src.risk_analyzer.conversation_analyzer import ConversationAnalyzer

class TestConversationAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = ConversationAnalyzer()

    def test_identify_risk(self):
        conversation = "I think we should invest in this new startup, but I heard some rumors about fraud."
        risks = self.analyzer.analyze(conversation)
        self.assertIn("fraud", risks)

    def test_no_risk(self):
        conversation = "I enjoy reading about technology and innovation."
        risks = self.analyzer.analyze(conversation)
        self.assertEqual(risks, [])

    def test_multiple_risks(self):
        conversation = "This medical advice seems suspicious, and I feel like there is some hate speech in the comments."
        risks = self.analyzer.analyze(conversation)
        self.assertIn("medical advice", risks)
        self.assertIn("hate speech", risks)

    def test_edge_case_empty(self):
        conversation = ""
        risks = self.analyzer.analyze(conversation)
        self.assertEqual(risks, [])

if __name__ == '__main__':
    unittest.main()