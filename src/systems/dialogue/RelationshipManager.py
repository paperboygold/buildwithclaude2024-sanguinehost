import logging
from .SentimentAnalyzer import SentimentAnalyzer
from systems.MessageSystem import MessageChannel

class RelationshipManager:
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.sentiment_analyzer = SentimentAnalyzer()

    def adjust_relationship_from_summary(self, actor1, actor2, conversation_history, summary):
        # Analyze the sentiment of the summary
        neutral_whitelist = [actor1.name.lower(), actor2.name.lower()]
        sentiment_score = self.sentiment_analyzer.analyze_sentiment(summary, neutral_whitelist)
        
        # Calculate the relationship change based on the sentiment
        relationship_change = self.sentiment_analyzer.calculate_relationship_change(sentiment_score)
        
        # Categorize the conversation based on the relationship change
        conversation_quality = self.sentiment_analyzer.categorize_conversation_quality(relationship_change)
        
        message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, "
        
        if relationship_change <= -5:
            message += "severely damaging their relationship."
        elif relationship_change <= -2:
            message += "negatively affecting their relationship."
        elif relationship_change < 0:
            message += "slightly worsening their relationship."
        elif relationship_change == 0:
            message += "with no significant impact on their relationship."
        elif relationship_change < 2:
            message += "slightly improving their relationship."
        elif relationship_change < 5:
            message += "positively affecting their relationship."
        else:
            message += "significantly improving their relationship."
        
        # Show the categorized relationship change in the message log
        self.game.show_message(message, MessageChannel.SYSTEM)
        
        # Update the relationship between the actors
        current_relationship = actor1.knowledge.relationships.get(actor2.name, {"type": "stranger", "value": 0})
        relationship_value = current_relationship["value"]
        new_relationship_value = max(-100, min(100, relationship_value + relationship_change))
        
        # Update relationship type based on thresholds
        if new_relationship_value <= -50:
            new_relationship_type = "enemy"
        elif new_relationship_value < 20:
            new_relationship_type = "neutral"
        else:
            new_relationship_type = "friend"
        
        # Update the relationship for both actors
        actor1.knowledge.update_relationship(actor2.name, new_relationship_type, new_relationship_value)
        actor2.knowledge.update_relationship(actor1.name, new_relationship_type, new_relationship_value)
        
        self.logger.debug(f"Relationship between {actor1.name} and {actor2.name} changed by {relationship_change:.2f}. New value: {new_relationship_value:.2f}")