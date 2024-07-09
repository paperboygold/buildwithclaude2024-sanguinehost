import logging
import tcod
import json
import textwrap
import traceback
from systems.MessageSystem import MessageChannel, Message
from components.ActorComponent import ActorComponent
from tcod.event import KeySym
from data.character_cards import character_cards, get_character_card
from .ConversationManager import ConversationManager
from .SentimentAnalyzer import SentimentAnalyzer
from .ConversationSummarizer import ConversationSummarizer
from .RelationshipManager import RelationshipManager
from entities.Actor import Actor

class DialogueSystem:
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.anthropic_client = game.anthropic_client
        self.conversation_manager = ConversationManager(game, self.anthropic_client)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.conversation_summarizer = ConversationSummarizer(game, self.anthropic_client)
        self.relationship_manager = RelationshipManager(game)

    def start_dialogue(self, actor):
        if self.game.disable_dialogue_system:
            return
        try:
            actor_component = actor.get_component(ActorComponent)
            actor_card = get_character_card(actor_component.character_card)
            self.logger.info(f"Starting dialogue with {actor.name}")
            self.logger.debug(f"Actor {actor.name} character card: {actor_card}")
            self.logger.debug(f"Actor {actor.name} knowledge: {actor.knowledge.get_summary()}")

            # Check if the actor is hostile before starting dialogue
            if actor.is_hostile(self.game.world.player):
                self.game.show_message(f"{actor.name} is hostile and refuses to talk!", MessageChannel.DIALOGUE)
                return

            self.game.show_message(f"You are now talking to {actor.name}", MessageChannel.DIALOGUE, sender=actor)
            
            while True:
                # Check if the actor has become hostile during the conversation
                if actor.is_hostile(self.game.world.player):
                    self.game.show_message(f"{actor.name} becomes hostile and ends the conversation!", MessageChannel.DIALOGUE)
                    break

                user_input = self.get_user_input("You: ")
                if user_input is None:  # User pressed Escape
                    self.logger.info(f"Dialogue with {actor.name} ended by user")
                    self.game.show_message("Dialogue ended.", MessageChannel.DIALOGUE, (0, 255, 255))
                    break
            
                self.logger.debug(f"Processing user input: {user_input}")
                self.show_dialogue(self.game.world.player, user_input)
            
                actor_component.dialogue_history.append({"role": "user", "content": user_input})
                
                # Process player's dialogue and get sentiment and relationship change
                player_sentiment, player_relationship_change = self.process_dialogue(self.game.world.player, actor, user_input)
                
                try:
                    relationship_info = ""
                    if actor.knowledge.known_actors:
                        other_actor_name, relationship_data = next(iter(actor.knowledge.known_actors.items()))
                        relationship = relationship_data["relationship"]
                        relationship_story = relationship_data["story"]
                        relationship_info = f"Your relationship with {other_actor_name}: {relationship.capitalize()}\n"
                        relationship_info += f"Relationship story: {relationship_story}\n"

                    # Add relationship change to the system prompt
                    relationship_info += f"Recent interaction impact:\n"
                    if abs(player_relationship_change) < 0.1:
                        impact = "Negligible"
                    elif abs(player_relationship_change) < 0.3:
                        impact = "Slight"
                    elif abs(player_relationship_change) < 0.6:
                        impact = "Moderate"
                    else:
                        impact = "Significant"
                    
                    relationship_info += f"- Magnitude: {impact}\n"
                    relationship_info += f"- Direction: {'Positive' if player_relationship_change >= 0 else 'Negative'}\n"
                    
                    if player_relationship_change < -0.2:
                        relationship_info += "- Emotional response: You are somewhat displeased by their words.\n"
                    elif player_relationship_change > 0.2:
                        relationship_info += "- Emotional response: You are somewhat pleased by their words.\n"
                    else:
                        relationship_info += "- Emotional response: You feel neutral about their words.\n"

                    # Use the character card information
                    system_prompt = f"""You are {actor.name}, an NPC in a roguelike game. 
                    Character: {json.dumps(actor_card, indent=2)}
                    Environmental knowledge: {actor.knowledge.get_summary()}
                    {relationship_info}
                    You are speaking to {self.game.world.player.name if isinstance(self.game.world.player, Actor) else 'someone'}.
                    Respond in character with extremely brief responses, typically 1-2 short sentences or 10 words or less. Be concise and direct.
                    Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what your character would say.
                    Respond to the other character's last statement while maintaining your character.
                    Your current relationship with the other character is {actor.knowledge.relationships.get(self.game.world.player.name, {"type": "stranger", "value": 0})["value"]}. Adjust your tone accordingly (more friendly for positive values, more cautious or hostile for negative values).
                    Your current emotional state is {actor_component.sentiment_history[-1]}. Let this influence your response.
                    """
                    
                    self.logger.info(f"API Request for {actor.name}:")
                    self.logger.info(f"System Prompt: {system_prompt}")
                    self.logger.debug(f"Dialogue history: {json.dumps(actor_component.dialogue_history, indent=2)}")
                    
                    request_body = {
                        "model": "claude-3-5-sonnet-20240620",
                        "max_tokens": 50,
                        "messages": actor_component.dialogue_history,  # Include the full conversation history
                        "system": system_prompt,
                        "temperature": 0.97,
                        "top_p": 1,
                        "stream": False,
                        "stop_sequences": ["\n\nHuman:", "\n\nSystem:", "\n\nAssistant:"]
                    }
                    
                    response = self.anthropic_client.messages.create(**request_body)
                    
                    self.logger.info(f"API Response for {actor.name}:")
                    self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
                    
                    actor_response = response.content[0].text if response.content else ""
                    actor_component.dialogue_history.append({"role": "assistant", "content": actor_response})
                    
                    self.show_dialogue(actor, actor_response)
                    
                    # Process NPC's dialogue
                    npc_sentiment, npc_relationship_change = self.process_dialogue(actor, self.game.world.player, actor_response)
                    
                    # Calculate the net relationship change
                    net_relationship_change = (player_relationship_change + npc_relationship_change) / 2

                    # Apply the relationship change immediately
                    current_relationship = actor.knowledge.relationships.get(self.game.world.player.name, {"type": "stranger", "value": 0})
                    relationship_value = current_relationship["value"]
                    new_relationship_value = max(-10, min(10, relationship_value + net_relationship_change))

                    # Update relationship type based on thresholds
                    if new_relationship_value <= -5:
                        new_relationship_type = "enemy"
                    elif new_relationship_value < 5:
                        new_relationship_type = "neutral"
                    else:
                        new_relationship_type = "friend"

                    # Update the relationship
                    actor.knowledge.update_relationship(self.game.world.player.name, new_relationship_type, new_relationship_value)
                    self.game.world.player.knowledge.update_relationship(actor.name, new_relationship_type, new_relationship_value)

                    # Log relationship change
                    self.logger.debug(f"{actor.name}'s relationship with {self.game.world.player.name} changed by {net_relationship_change:.2f}. New value: {new_relationship_value:.2f}")

                    # Display current relationship status
                    relationship_value = round(new_relationship_value, 1)
                    self.game.show_message(f"Current relationship with {actor.name}: {relationship_value}", MessageChannel.SYSTEM)
                    
                    # Check if the dialogue should end due to aggression
                    if actor.is_hostile(self.game.world.player) and actor.get_recent_combat_memory():
                        self.game.show_message(f"{actor.name} becomes hostile and ends the conversation!", MessageChannel.DIALOGUE)
                        break
                except Exception as e:
                    self.logger.error(f"Error in AI response: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                    self.game.show_message(f"Error: Unable to get NPC response", MessageChannel.SYSTEM, (255, 0, 0))

            # Summarize the conversation only if there were any messages
            if actor_component.dialogue_history:
                summary = self.conversation_summarizer.generate_conversation_summary(self.game.world.player, actor, actor_component.dialogue_history)
                self.add_conversation_memory(self.game.world.player, actor, summary)
                self.logger.info(f"Conversation summary between Player and {actor.name}: {summary}")

                # Apply the final relationship adjustment based on the conversation summary
                self.relationship_manager.adjust_relationship_from_summary(self.game.world.player, actor, actor_component.dialogue_history, summary)
            else:
                self.logger.info(f"Dialogue with {actor.name} ended without any messages exchanged.")

            # Clear the dialogue history
            actor_component.dialogue_history = []

        except Exception as e:
            self.logger.error(f"Error in dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.game.show_message(f"An error occurred during dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def get_player_choice(self, prompt):
        self.game.show_message(prompt, MessageChannel.SYSTEM, (255, 255, 0))
        self.game.show_message("Press Y to listen or N to ignore.", MessageChannel.SYSTEM, (255, 255, 0))
        
        while True:
            for event in tcod.event.wait():
                if event.type == "QUIT":
                    raise SystemExit()
                elif event.type == "KEYDOWN":
                    if event.sym == KeySym.y:
                        return True
                    elif event.sym == KeySym.n:
                        return False
            
            self.game.render_system.render()

    def get_user_input(self, prompt):
        user_input = ""
        max_input_length = self.game.width * 3  # Allow for multiple lines
        input_lines = []
        cursor_pos = 0
        ignore_next_i = True  # Add this flag

        while True:
            # Wrap the current input
            wrapped_lines = textwrap.wrap(prompt + user_input, width=self.game.width - 2)
            
            # Update the message log with the wrapped input
            self.game.message_system.message_log = self.game.message_system.message_log[:-len(input_lines)] if input_lines else self.game.message_system.message_log
            input_lines = [Message(line, MessageChannel.SYSTEM, (0, 255, 0)) for line in wrapped_lines]  # Change color to green
            self.game.message_system.message_log.extend(input_lines)

            # Ensure we don't exceed the visible log lines
            while len(self.game.message_system.message_log) > self.game.visible_log_lines:
                self.game.message_system.message_log.pop(0)

            self.game.render_system.render()  # Render the game state

            for event in tcod.event.wait():
                if event.type == "QUIT":
                    raise SystemExit()
                elif event.type == "KEYDOWN":
                    if event.sym == KeySym.RETURN and user_input:
                        # Remove temporary input lines
                        self.game.message_system.message_log = self.game.message_system.message_log[:-len(input_lines)]
                        # Don't add the final input as a message here
                        return user_input
                    elif event.sym == KeySym.BACKSPACE:
                        if user_input:
                            user_input = user_input[:cursor_pos-1] + user_input[cursor_pos:]
                            cursor_pos = max(0, cursor_pos - 1)
                    elif event.sym == KeySym.ESCAPE:
                        self.game.message_system.message_log = self.game.message_system.message_log[:-len(input_lines)]
                        return None
                elif event.type == "TEXTINPUT":
                    if len(user_input) < max_input_length:
                        if ignore_next_i and event.text == 'i':
                            ignore_next_i = False  # Reset the flag
                        else:
                            user_input = user_input[:cursor_pos] + event.text + user_input[cursor_pos:]
                            cursor_pos += len(event.text)

            # Add cursor to the end of the last line
            if input_lines:
                last_line = input_lines[-1].text
                cursor_line = last_line[:cursor_pos] + "_" + last_line[cursor_pos:]
                self.game.message_system.message_log[-1] = Message(cursor_line, MessageChannel.SYSTEM, (0, 255, 0))  # Change color to green

    def add_conversation_memory(self, actor1, actor2, summary):
        actor1.knowledge.add_conversation_memory(f"Talked with {actor2.name}: {summary}")
        actor2.knowledge.add_conversation_memory(f"Talked with {actor1.name}: {summary}")
        self.logger.info(f"Added conversation memory for {actor1.name} and {actor2.name}: {summary}")

    def process_dialogue(self, speaker, listener, dialogue):
        # Define a neutral whitelist for names, titles, and fantasy terms
        neutral_whitelist = ["the destroyer", "the enigma", "the sage", "shadows", "age of shadows", "destiny", "dance"]
        
        # Add character names to the neutral whitelist
        for card in character_cards.values():
            neutral_whitelist.append(card['name'].lower())
        
        compound_score = self.sentiment_analyzer.analyze_sentiment(dialogue, neutral_whitelist)

        # Get the listener's component
        listener_component = listener.get_component(ActorComponent)

        # Update the moving average of sentiment scores
        if not hasattr(listener_component, 'sentiment_history'):
            listener_component.sentiment_history = []
        listener_component.sentiment_history.append(compound_score)
        if len(listener_component.sentiment_history) > 5:  # Keep last 5 interactions
            listener_component.sentiment_history.pop(0)

        # Calculate the average sentiment
        avg_sentiment = sum(listener_component.sentiment_history) / len(listener_component.sentiment_history)

        # Calculate the relationship change
        context_modifier = 1.0
        if "apology" in dialogue.lower() or "sorry" in dialogue.lower():
            context_modifier = 1.5
        elif "thank" in dialogue.lower() or "appreciate" in dialogue.lower():
            context_modifier = 1.5
        
        relationship_change = self.sentiment_analyzer.calculate_relationship_change(
            compound_score,  # Use the current sentiment, not the average
            context_modifier,
            listener.knowledge.relationships.get(speaker.name, {"type": "stranger", "value": 0})["value"]
        )

        # Log the relationship change for debugging
        self.logger.debug(f"Relationship change for {listener.name}: {relationship_change:.2f}")

        # Return the sentiment score and relationship change without applying it
        return compound_score, relationship_change

    def show_dialogue(self, speaker, message):
        formatted_message = f"\n{speaker.name}: \"{message}\"\n"
        self.game.show_message(formatted_message, MessageChannel.DIALOGUE, sender=speaker)