import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SentimentAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.sentiment_history = []

    def analyze_sentiment(self, dialogue, neutral_whitelist):
        sanitized_dialogue = dialogue.lower()
        for word in neutral_whitelist:
            sanitized_dialogue = sanitized_dialogue.replace(word, "")
        
        sentiment_scores = self.sentiment_analyzer.polarity_scores(sanitized_dialogue)
        compound_score = sentiment_scores['compound']
        
        self.sentiment_history.append(compound_score)
        if len(self.sentiment_history) > 5:
            self.sentiment_history.pop(0)
        
        return compound_score

    def calculate_relationship_change(self, sentiment_score, context_modifier=1.0):
        avg_sentiment = sum(self.sentiment_history) / len(self.sentiment_history)
        
        # Adjust the relationship change calculation
        if abs(avg_sentiment) < 0.1:
            relationship_change = 0  # Consider very small changes as neutral
        elif avg_sentiment < 0:
            relationship_change = -1 * (abs(avg_sentiment) ** 0.7) * 3
        else:
            relationship_change = avg_sentiment * 2
        
        relationship_change = round(relationship_change, 2)
        relationship_change = max(-5, min(3, relationship_change))  # Narrower range
        
        return relationship_change * context_modifier

    def categorize_conversation_quality(self, relationship_change):
        if relationship_change <= -3:
            return "negative"
        elif relationship_change <= -1:
            return "slightly negative"
        elif relationship_change < 1:
            return "neutral"
        elif relationship_change < 3:
            return "slightly positive"
        else:
            return "positive"

    def get_impact_description(self, relationship_change):
        abs_change = abs(relationship_change)
        if abs_change < 0.5:
            return "Negligible"
        elif abs_change < 1:
            return "Slight"
        elif abs_change < 2:
            return "Moderate"
        else:
            return "Significant"