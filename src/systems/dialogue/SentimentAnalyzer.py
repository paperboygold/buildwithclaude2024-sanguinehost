import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

class SentimentAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.sentiment_history = []

    def analyze_sentiment(self, dialogue, neutral_whitelist):
        self.logger.debug(f"Analyzing sentiment for dialogue: '{dialogue}'")
        self.logger.debug(f"Neutral whitelist: {neutral_whitelist}")
        
        sanitized_dialogue = dialogue.lower()
        for word in neutral_whitelist:
            sanitized_dialogue = sanitized_dialogue.replace(word, "")
        
        self.logger.debug(f"Sanitized dialogue: '{sanitized_dialogue}'")
        
        # Custom fantasy lexicon with sentiment scores
        fantasy_lexicon = {
            "quest": 0.3, "adventure": 0.4, "magic": 0.2, "curse": -0.3,
            "dragon": 0.1, "sword": 0.1, "spell": 0.2, "potion": 0.1,
            "dark": -0.2, "light": 0.2, "evil": -0.4, "good": 0.4,
            "ancient": 0.1, "prophecy": 0.2, "destiny": 0.3, "doom": -0.3,
            "illuminate": 0.3, "insight": 0.4, "wisdom": 0.4, "star": 0.2,
            "path": 0.1, "traveler": 0.1, "journey": 0.2, "mystic": 0.2,
            "enchant": 0.3, "legend": 0.2, "lore": 0.1, "artifact": 0.2
        }
        
        sentiment_scores = self.sentiment_analyzer.polarity_scores(sanitized_dialogue)
        self.logger.debug(f"Initial sentiment scores: {sentiment_scores}")
        
        # Adjust sentiment based on fantasy lexicon
        for word, score in fantasy_lexicon.items():
            if word in sanitized_dialogue:
                sentiment_scores['compound'] += score
                self.logger.debug(f"Adjusted sentiment for '{word}' by {score}")
        
        # Normalize the compound score
        compound_score = max(-1, min(1, sentiment_scores['compound']))
        
        self.logger.info(f"Final compound sentiment score: {compound_score}")
        
        self.sentiment_history.append(compound_score)
        if len(self.sentiment_history) > 5:
            self.sentiment_history.pop(0)
        
        self.logger.debug(f"Updated sentiment history: {self.sentiment_history}")
        
        return compound_score

    def calculate_relationship_change(self, sentiment_score, context_modifier=1.0, current_relationship=0):
        self.logger.debug(f"Calculating relationship change. Sentiment score: {sentiment_score}, Context modifier: {context_modifier}, Current relationship: {current_relationship}")
        
        # Calculate weighted average of sentiment history
        weights = [0.2, 0.3, 0.5]  # More recent interactions have higher weights
        weighted_avg_sentiment = sum(s * w for s, w in zip(self.sentiment_history[-3:], weights)) / sum(weights)
        
        self.logger.debug(f"Weighted average sentiment: {weighted_avg_sentiment}")
        
        # Adjust the base change calculation
        base_change = sentiment_score * 0.6  # Reduce the impact of current interaction

        # Make negative changes more impactful, but less than before
        if sentiment_score < 0:
            base_change *= 1.2  # Increase the impact of negative interactions, but not as much

        # Apply diminishing returns
        if len(self.sentiment_history) > 3:
            diminishing_factor = 0.95 ** (len(self.sentiment_history) - 3)
            base_change *= diminishing_factor
        
        # Adjust for extreme values and sudden shifts
        if abs(sentiment_score) > 0.8:
            base_change *= 1.2
        
        # Apply context modifier
        final_change = base_change * context_modifier
        
        # Adjust the capping logic
        if final_change > 0:
            final_change = min(0.4, final_change)  # Cap positive changes at 0.4
        else:
            final_change = max(-0.6, final_change)  # Cap negative changes at -0.6
        
        # Consider the overall conversation trend
        if weighted_avg_sentiment > 0.3 and final_change < 0:
            final_change *= 0.5  # Reduce negative impact if the overall trend is positive
        elif weighted_avg_sentiment < -0.3 and final_change > 0:
            final_change *= 0.5  # Reduce positive impact if the overall trend is negative

        self.logger.info(f"Final relationship change: {final_change:.2f}")
        return final_change

    def update_sentiment_history(self, sentiment_score):
        self.sentiment_history.append(sentiment_score)
        if len(self.sentiment_history) > 10:  # Keep only the last 10 scores
            self.sentiment_history.pop(0)

    def categorize_conversation_quality(self, relationship_change):
        self.logger.debug(f"Categorizing conversation quality. Relationship change: {relationship_change}")
        
        if relationship_change <= -3:
            category = "negative"
        elif relationship_change <= -1:
            category = "slightly negative"
        elif relationship_change < 1:
            category = "neutral"
        elif relationship_change < 3:
            category = "slightly positive"
        else:
            category = "positive"
        
        self.logger.info(f"Conversation quality categorized as: {category}")
        return category

    def get_impact_description(self, relationship_change):
        self.logger.debug(f"Getting impact description. Relationship change: {relationship_change}")
        
        abs_change = abs(relationship_change)
        if abs_change < 0.1:
            impact = "Negligible"
        elif abs_change < 0.3:
            impact = "Very Slight"
        elif abs_change < 0.5:
            impact = "Slight"
        elif abs_change < 1:
            impact = "Noticeable"
        elif abs_change < 2:
            impact = "Moderate"
        else:
            impact = "Significant"
        
        self.logger.info(f"Impact described as: {impact}")
        return impact