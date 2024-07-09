import logging
import random
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
        new_relationship_type = self.get_relationship_type(new_relationship_value)
        
        # Update the relationship for both actors
        actor1.knowledge.update_relationship(actor2.name, new_relationship_type, new_relationship_value)
        actor2.knowledge.update_relationship(actor1.name, new_relationship_type, new_relationship_value)
        
        self.logger.debug(f"Relationship between {actor1.name} and {actor2.name} changed by {relationship_change:.2f}. New value: {new_relationship_value:.2f}")
        
        return final_relationship, message

    def get_relationship(self, actor1, actor2):
        current_relationship = actor1.knowledge.relationships.get(actor2.name, {"type": "stranger", "value": 0})
        return current_relationship["value"]

    def will_intervene_in_combat(self, witness, attacker, target):
        witness_relationship_with_attacker = self.get_relationship(witness, attacker)
        witness_relationship_with_target = self.get_relationship(witness, target)

        # Calculate the relationship difference
        relationship_difference = witness_relationship_with_target - witness_relationship_with_attacker

        # Base intervention chance
        intervention_chance = 0.5

        # Adjust intervention chance based on relationships
        if relationship_difference > 0:  # Witness likes the target more
            intervention_chance += min(relationship_difference / 100, 0.4)
        else:  # Witness likes the attacker more or equally
            intervention_chance -= min(abs(relationship_difference) / 100, 0.4)

        # Consider witness's aggression type
        if witness.aggression_type == "peaceful":
            intervention_chance += 0.2
        elif witness.aggression_type == "hostile":
            intervention_chance -= 0.2

        # Final decision
        return random.random() < intervention_chance

    def update_relationship_after_combat(self, actor1, actor2, combat_result):
        relationship_change = 0
        if combat_result == "victory":
            relationship_change = -30  # Losing a fight significantly decreases relationship
        elif combat_result == "defeat":
            relationship_change = -15  # Winning a fight also decreases relationship, but less so

        current_relationship = self.get_relationship(actor1, actor2)
        new_relationship_value = max(-100, min(100, current_relationship + relationship_change))
        new_relationship_type = self.get_relationship_type(new_relationship_value)

        actor1.knowledge.update_relationship(actor2.name, new_relationship_type, new_relationship_value)
        actor2.knowledge.update_relationship(actor1.name, new_relationship_type, new_relationship_value)

        self.logger.debug(f"Relationship between {actor1.name} and {actor2.name} changed by {relationship_change} due to combat. New value: {new_relationship_value}")

    def get_relationship_type(self, value):
        if value < -80:
            return "arch-nemesis"
        elif value < -60:
            return "sworn enemy"
        elif value < -40:
            return "rival"
        elif value < -20:
            return "antagonist"
        elif value < -5:
            return "unfriendly"
        elif value < 5:
            return "stranger"
        elif value < 15:
            return "acquaintance"
        elif value < 30:
            return "friendly"
        elif value < 45:
            return "good friend"
        elif value < 60:
            return "close friend"
        elif value < 75:
            return "confidant"
        elif value < 85:
            return "ally"
        elif value < 95:
            return "loyal ally"
        else:
            return "soulmate"