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
        
        # Get the initial relationship value
        initial_relationship = self.get_relationship(actor1, actor2)
        
        # Calculate the relationship change based on the sentiment
        relationship_change = self.sentiment_analyzer.calculate_relationship_change(
            sentiment_score, 
            context_modifier=1.0, 
            current_relationship=initial_relationship
        )
        
        # Apply the change
        final_relationship = initial_relationship + relationship_change
        
        # Categorize the conversation based on the relationship change
        conversation_quality = self.sentiment_analyzer.categorize_conversation_quality(relationship_change)
        impact_description = self.sentiment_analyzer.get_impact_description(relationship_change)
        
        message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, "
        message += f"having a {impact_description.lower()} impact on their relationship."
        
        # Show the categorized relationship change in the message log
        self.game.show_message(message, MessageChannel.SYSTEM)
        
        # Update the relationship between the actors
        current_relationship = actor1.knowledge.relationships.get(actor2.name, {"type": "stranger", "value": 0})
        relationship_value = current_relationship["value"]
        new_relationship_value = max(-100, min(100, relationship_value + relationship_change))
        
        # Update relationship type based on thresholds
        if new_relationship_value <= -80:
            new_relationship_type = "arch-nemesis"
        elif new_relationship_value <= -60:
            new_relationship_type = "sworn enemy"
        elif new_relationship_value <= -40:
            new_relationship_type = "rival"
        elif new_relationship_value <= -20:
            new_relationship_type = "antagonist"
        elif new_relationship_value < 0:
            new_relationship_type = "unfriendly"
        elif new_relationship_value < 10:
            new_relationship_type = "neutral"
        elif new_relationship_value < 20:
            new_relationship_type = "acquaintance"
        elif new_relationship_value < 30:
            new_relationship_type = "friendly"
        elif new_relationship_value < 40:
            new_relationship_type = "good friend"
        elif new_relationship_value < 50:
            new_relationship_type = "close friend"
        elif new_relationship_value < 60:
            new_relationship_type = "confidant"
        elif new_relationship_value < 70:
            new_relationship_type = "best friend"
        elif new_relationship_value < 80:
            new_relationship_type = "loyal ally"
        else:
            new_relationship_type = "soulmate"
        
        # Update the relationship for both actors
        actor1.knowledge.update_relationship(actor2.name, new_relationship_type, new_relationship_value)
        actor2.knowledge.update_relationship(actor1.name, new_relationship_type, new_relationship_value)
        
        self.logger.debug(f"Relationship between {actor1.name} and {actor2.name} changed by {relationship_change:.2f}. New value: {new_relationship_value:.2f}")
        
        return final_relationship, message

    def get_relationship(self, actor1, actor2):
        current_relationship = actor1.knowledge.relationships.get(actor2.name, {"type": "stranger", "value": 0})
        return current_relationship["value"]