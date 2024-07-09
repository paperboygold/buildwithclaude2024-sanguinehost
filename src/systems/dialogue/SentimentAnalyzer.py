import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SentimentAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

    def analyze_sentiment(self, dialogue, neutral_whitelist):
        # Remove whitelisted words from the dialogue for sentiment analysis
        sanitized_dialogue = dialogue.lower()
        for word in neutral_whitelist:
            sanitized_dialogue = sanitized_dialogue.replace(word, "")
        
        sentiment_scores = self.sentiment_analyzer.polarity_scores(sanitized_dialogue)
        compound_score = sentiment_scores['compound']
        
        return compound_score

    def calculate_relationship_change(self, sentiment_score, context_modifier=1.0):
        relationship_change = round(sentiment_score * 2, 1)
        relationship_change = max(-3, min(3, relationship_change))
        
        return relationship_change * context_modifier

    def map_sentiment_to_relationship(self, sentiment):
        max_change = 2  # Reduced max change for more gradual relationship shifts
        if sentiment > 0:
            change = min(int((sentiment ** 0.5) * 2.5), max_change)
        else:
            change = max(int(-((-sentiment) ** 0.5) * 2.5), -max_change)
        return change

    def categorize_conversation_quality(self, relationship_change):
        if relationship_change <= -5:
            return "terrible"
        elif relationship_change <= -2:
            return "bad"
        elif relationship_change < 0:
            return "somewhat negative"
        elif relationship_change == 0:
            return "neutral"
        elif relationship_change < 2:
            return "somewhat positive"
        elif relationship_change < 5:
            return "good"
        else:
            return "great"