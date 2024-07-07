import logging
import tcod
import json
import time
import textwrap
import traceback
import random
from systems.MessageSystem import MessageChannel, Message
from components.ActorComponent import ActorComponent, ActorState, EmotionalState
from tcod.event import KeySym
from entities.Actor import Actor
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from data.character_cards import character_cards, get_character_card

class DialogueSystem:
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.anthropic_client = game.anthropic_client

    def start_dialogue(self, actor):
        if self.game.disable_dialogue_system:
            return
        try:
            actor_component = actor.get_component(ActorComponent)
            actor_card = get_character_card(actor_component.character_card)
            self.logger.info(f"Starting dialogue with {actor.name}")
            self.logger.debug(f"Actor {actor.name} character card: {actor_card}")
            self.logger.debug(f"Actor {actor.name} knowledge: {actor.knowledge.get_summary()}")
            self.game.show_message(f"You are now talking to {actor.name}", MessageChannel.DIALOGUE, sender=actor)
            
            while True:
                user_input = self.get_user_input("You: ")
                if user_input is None:  # User pressed Escape
                    self.logger.info(f"Dialogue with {actor.name} ended by user")
                    self.game.show_message("Dialogue ended.", MessageChannel.DIALOGUE, (0, 255, 255))
                    break
            
                self.logger.debug(f"Processing user input: {user_input}")
                self.show_dialogue(self.game.world.player, user_input)
            
                actor_component.dialogue_history.append({"role": "user", "content": user_input})
                
                # Process player's dialogue and get relationship change
                relationship_change = self.process_dialogue(self.game.world.player, actor, user_input)
                
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
                    if abs(relationship_change) < 0.1:
                        impact = "Negligible"
                    elif abs(relationship_change) < 0.3:
                        impact = "Slight"
                    elif abs(relationship_change) < 0.6:
                        impact = "Moderate"
                    else:
                        impact = "Significant"
                    
                    relationship_info += f"- Magnitude: {impact}\n"
                    relationship_info += f"- Direction: {'Positive' if relationship_change >= 0 else 'Negative'}\n"
                    
                    if relationship_change < -0.2:
                        relationship_info += "- Emotional response: You are somewhat displeased by their words.\n"
                    elif relationship_change > 0.2:
                        relationship_info += "- Emotional response: You are somewhat pleased by their words.\n"
                    else:
                        relationship_info += "- Emotional response: You feel neutral about their words.\n"

                    # Use the character card information
                    system_prompt = f"""You are {actor.name}, an NPC in a roguelike game. 
Character: {json.dumps(actor_card, indent=2)}
Environmental knowledge: {actor.knowledge.get_summary()}
{relationship_info}
Respond in character with extremely brief responses, typically 1-2 short sentences or 10 words or less. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what your character would say.
You may reference your recent combat experiences if relevant to the conversation."""
                    
                    self.logger.info(f"API Request for {actor.name}:")
                    self.logger.info(f"System Prompt: {system_prompt}")
                    self.logger.debug(f"Dialogue history: {json.dumps(actor_component.dialogue_history, indent=2)}")
                    
                    request_body = {
                        "model": "claude-3-5-sonnet-20240620",
                        "max_tokens": 50,
                        "messages": actor_component.dialogue_history,
                        "system": system_prompt,
                        "temperature": 0.93,
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
                    self.process_dialogue(actor, self.game.world.player, actor_response)
                    
                    # Display current relationship status
                    relationship_value = round(actor.knowledge.relationships.get(self.game.world.player.name, 0), 1)
                    self.game.show_message(f"Current relationship with {actor.name}: {relationship_value}", MessageChannel.SYSTEM)
                    
                    # Check if the dialogue should end due to aggression
                    if actor_component.state == ActorState.AGGRESSIVE:
                        self.game.show_message(f"{actor.name} becomes hostile and ends the conversation!", MessageChannel.DIALOGUE)
                        break
                except Exception as e:
                    self.logger.error(f"Error in AI response: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                    self.game.show_message(f"Error: Unable to get NPC response", MessageChannel.SYSTEM, (255, 0, 0))

            # Summarize the conversation
            if actor_component.dialogue_history:
                summary = self.summarize_full_conversation(self.game.world.player, actor, actor_component.dialogue_history)
                self.add_conversation_memory(self.game.world.player, actor, summary)
                self.logger.info(f"Conversation summary between Player and {actor.name}: {summary}")

            # Apply the final relationship adjustment based on the conversation summary
            self.adjust_relationship_from_summary(self.game.world.player, actor, summary)

            # Clear the dialogue history
            actor_component.dialogue_history = []

        except Exception as e:
            self.logger.error(f"Error in dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.game.show_message(f"An error occurred during dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def start_actor_dialogue(self, actor1, actor2):
        if self.game.disable_dialogue_system:
            return
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            
            # Check if either actor is in combat
            if actor1_component.state == ActorState.AGGRESSIVE or actor2_component.state == ActorState.AGGRESSIVE:
                return  # Skip dialogue if either actor is in combat
            
            current_time = time.time()
            if current_time - actor1_component.last_conversation_time < actor1_component.conversation_cooldown or \
               current_time - actor2_component.last_conversation_time < actor2_component.conversation_cooldown:
                return  # Skip if either actor is on cooldown

            # Calculate conversation likelihood and check faction compatibility
            if self.should_start_conversation(actor1, actor2):
                actor1_component.last_conversation_time = current_time
                actor2_component.last_conversation_time = current_time

                player_can_see = self.game.world.game_map.is_in_fov(int(self.game.world.player.x), int(self.game.world.player.y)) and \
                                 (self.game.world.game_map.is_in_fov(int(actor1.x), int(actor1.y)) or 
                                  self.game.world.game_map.is_in_fov(int(actor2.x), int(actor2.y)))

                self.logger.debug(f"Initiating dialogue between {actor1.name} and {actor2.name}")
                self.logger.debug(f"Player can see conversation: {player_can_see}")

                if player_can_see:
                    choice = self.get_player_choice(f"{actor1.name} and {actor2.name} are about to have a conversation. Do you want to listen?")
                    if choice:
                        self.game.show_message(f"{actor1.name} and {actor2.name} have started a conversation.", MessageChannel.DIALOGUE, sender=actor1)
                    else:
                        summary = self.summarize_conversation(actor1, actor2)
                        if summary:  # Check if summary is not None
                            self.add_conversation_memory(actor1, actor2, summary)
                            self.adjust_relationship_from_summary(actor1, actor2, summary)
                        else:
                            self.logger.error(f"Failed to generate summary for conversation between {actor1.name} and {actor2.name}")
                        return
                else:
                    summary = self.summarize_conversation(actor1, actor2)
                    if summary:  # Check if summary is not None
                        self.add_conversation_memory(actor1, actor2, summary)
                        self.adjust_relationship_from_summary(actor1, actor2, summary)
                    else:
                        self.logger.error(f"Failed to generate summary for conversation between {actor1.name} and {actor2.name}")
                    return

                relationship_info = actor1.knowledge.get_relationship_story(actor2.name) or ""
                actor2_info = actor1.knowledge.known_actors.get(actor2.name, {})
                
                system_prompt = f"""You are simulating a conversation between {actor1.name} and {actor2.name} in a dungeon setting.
{actor1.name}'s character: {actor1_component.character_card}
{actor2.name}'s character: {actor2_component.character_card}
Their relationship: {relationship_info}
{actor1.name}'s knowledge of {actor2.name}: Aggressive: {actor2_info.get('is_aggressive', False)}, Targeting: {actor2_info.get('is_targeting', False)}, Last seen: {actor2_info.get('last_seen_position', 'Unknown')}, Proximity: {actor2_info.get('proximity', 'Unknown')}
Environmental knowledge: {actor1.knowledge.get_summary()}
Keep responses brief and in character, typically 1-2 short sentences or 10-15 words. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what the character would say."""

                # Define the initial prompt
                actor_prompt = f"You are {actor1.name}. Start a conversation with {actor2.name} in character, briefly and naturally."
                
                self.logger.info(f"Starting actor dialogue between {actor1.name} and {actor2.name}")
                self.logger.debug(f"Actor1 {actor1.name} character card: {actor1_component.character_card}")
                self.logger.debug(f"Actor2 {actor2.name} character card: {actor2_component.character_card}")
                self.logger.debug(f"Relationship info: {relationship_info}")
                self.logger.info(f"API Request for {actor1.name}:")
                self.logger.info(f"System Prompt: {system_prompt}")
                self.logger.info(f"Actor Prompt: {actor_prompt}")
                
                request_body = {
                    "model": "claude-3-5-sonnet-20240620",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": actor_prompt}],
                    "system": system_prompt,
                    "temperature": 0.93
                }
                
                response = self.anthropic_client.messages.create(**request_body)
                
                self.logger.info(f"API Response for {actor1.name}:")
                self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
                
                actor_response = response.content[0].text if response.content else ""

                # Start a new conversation
                conversation = [
                    {"role": "user", "content": actor_prompt},
                    {"role": "assistant", "content": actor_response}
                ]
                
                if player_can_see:
                    self.show_dialogue(actor1, actor_response)

                # Store the conversation for future reference
                actor1_component.current_conversation = conversation
                actor2_component.current_conversation = conversation
                actor1_component.conversation_partner = actor2
                actor2_component.conversation_partner = actor1
                actor1_component.conversation_turns = 1
                actor2_component.conversation_turns = 0

                self.logger.info(f"Conversation started. Turn counts: {actor1.name} = 1, {actor2.name} = 0")

        except Exception as e:
            self.logger.error(f"Error in actor dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            if player_can_see:
                self.game.show_message(f"An error occurred during actor dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def should_start_conversation(self, actor1, actor2):
        actor1_likelihood = actor1.character_card['aggression_type']['conversation_likelihood']
        actor2_likelihood = actor2.character_card['aggression_type']['conversation_likelihood']
        combined_likelihood = (actor1_likelihood + actor2_likelihood) / 2
        faction_compatible = self.check_faction_compatibility(actor1, actor2)
        return random.random() < combined_likelihood and faction_compatible

    def check_faction_compatibility(self, actor1, actor2):
        faction1 = actor1.character_card['faction']
        faction2 = actor2.character_card['faction']
        
        # Define faction relationships (this could be moved to a separate configuration file)
        faction_relationships = {
            "sages": ["sages", "enigmas"],
            "enigmas": ["sages", "enigmas", "monsters"],
            "monsters": ["monsters", "enigmas"]
        }
        
        return faction2 in faction_relationships.get(faction1, [])

    def summarize_conversation(self, actor1, actor2):
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            
            system_prompt = f"""Summarize a brief, unique conversation between {actor1.name} and {actor2.name} in a dungeon setting.
            {actor1.name}'s character: {actor1_component.character_card}
            {actor2.name}'s character: {actor2_component.character_card}
            Their relationship: {actor1.knowledge.get_relationship_story(actor2.name) or ""}
            Environmental knowledge: {actor1.knowledge.get_summary()}
            Provide a single sentence summary of their conversation, focusing on a specific topic or outcome.
            Make sure the summary is different from previous conversations."""

            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Summarize the conversation."}],
                "system": system_prompt,
                "temperature": 0.97
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            summary = response.content[0].text if response.content else None

            if summary:
                self.game.show_message(summary, MessageChannel.DIALOGUE)
                return summary
            else:
                self.logger.error("Failed to generate conversation summary: Empty response")
                return None

        except Exception as e:
            self.logger.error(f"Error in summarizing conversation: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return None

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

    def continue_actor_dialogue(self, actor1, actor2):
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            player_can_see = self.game.world.game_map.is_in_fov(int(self.game.world.player.x), int(self.game.world.player.y)) and \
                             (self.game.world.game_map.is_in_fov(int(actor1.x), int(actor1.y)) or 
                              self.game.world.game_map.is_in_fov(int(actor2.x), int(actor2.y)))

            conversation = actor1_component.current_conversation
            self.logger.info(f"Continuing actor dialogue between {actor1.name} and {actor2.name}")
            self.logger.debug(f"Current conversation state: {json.dumps(conversation, indent=2)}")

            # Determine which actor should speak next
            current_actor = actor2 if actor1_component.conversation_turns > actor2_component.conversation_turns else actor1
            other_actor = actor1 if current_actor == actor2 else actor2

            self.logger.debug(f"Conversation turns - {actor1.name}: {actor1_component.conversation_turns}, {actor2.name}: {actor2_component.conversation_turns}")
            self.logger.debug(f"Current speaker: {current_actor.name}, Responding to: {other_actor.name}")

            # Check the role of the last message and set the next role accordingly
            last_role = conversation[-1]["role"] if conversation else "assistant"
            next_role = "user" if last_role == "assistant" else "assistant"

            # Add the prompt for the current actor to speak next
            if next_role == "user":
                conversation.append({
                    "role": "user",
                    "content": f"{current_actor.name}, respond to {other_actor.name}'s last statement."
                })

            system_prompt = f"""You are {current_actor.name} in a conversation with {other_actor.name} in a dungeon setting.
{current_actor.name}'s character: {current_actor.get_component(ActorComponent).character_card}
Keep responses brief and in character, typically 1-2 short sentences or 10-15 words. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what the character would say."""

            self.logger.info(f"API Request for {current_actor.name}:")
            self.logger.info(f"System Prompt: {system_prompt}")
            self.logger.info(f"Messages: {json.dumps(conversation, indent=2)}")
            
            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": conversation,
                "system": system_prompt,
                "temperature": 0.93
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            
            self.logger.info(f"API Response for {current_actor.name}:")
            self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
            
            actor_response = response.content[0].text if response.content else ""
            
            if actor_response.strip():  # Only add non-empty responses
                conversation.append({"role": "assistant", "content": actor_response})
                
                if player_can_see:
                    self.show_dialogue(current_actor, actor_response)

            # Update the conversation for both actors
            actor1_component.current_conversation = conversation
            actor2_component.current_conversation = conversation

            # Increment the conversation turn counter for the current actor
            current_actor.get_component(ActorComponent).conversation_turns += 1

            # Check if the conversation should end
            if actor1_component.conversation_turns + actor2_component.conversation_turns >= 6:
                conversation_history = actor1_component.current_conversation
                summary = self.end_conversation(actor1, actor2, conversation_history)
                if player_can_see:
                    self.game.show_message(f"Conversation summary: {summary}", MessageChannel.DIALOGUE)
                return

        except Exception as e:
            self.logger.error(f"Error in continuing actor dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            if player_can_see:
                self.game.show_message(f"An error occurred during actor dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def end_conversation(self, actor1, actor2, conversation_history):
        self.end_actor_conversation(actor1, actor2)
        summary = self.generate_conversation_summary(actor1, actor2, conversation_history)
        self.add_conversation_memory(actor1, actor2, summary)
        self.adjust_relationship_from_summary(actor1, actor2, summary)
        self.logger.info(f"Conversation ended between {actor1.name} and {actor2.name}. Summary: {summary}")
        return summary

    def end_actor_conversation(self, actor1, actor2):
        actor1_component = actor1.get_component(ActorComponent)
        actor2_component = actor2.get_component(ActorComponent)
        
        actor1_component.current_conversation = None
        actor2_component.current_conversation = None
        actor1_component.conversation_partner = None
        actor2_component.conversation_partner = None
        actor1_component.conversation_turns = 0
        actor2_component.conversation_turns = 0
        
        player_can_see = self.game.world.game_map.is_in_fov(int(self.game.world.player.x), int(self.game.world.player.y)) and \
                         (self.game.world.game_map.is_in_fov(int(actor1.x), int(actor1.y)) or 
                          self.game.world.game_map.is_in_fov(int(actor2.x), int(actor2.y)))
        
        self.logger.info(f"Ending conversation between {actor1.name} and {actor2.name}")
        self.logger.debug(f"Player can see conversation end: {player_can_see}")
        
        if player_can_see:
            self.game.show_message(f"{actor1.name} and {actor2.name} have ended their conversation.", MessageChannel.DIALOGUE)

    def generate_conversation_summary(self, actor1, actor2, conversation_history):
        try:
            self.logger.info(f"Generating summary for conversation between {actor1.name} and {actor2.name}")
            system_prompt = f"""Summarize the conversation between {actor1.name} and {actor2.name} in a dungeon setting.
            Provide a single sentence summary of their conversation, focusing on the main topic or outcome.
            Do not include any dialogue or character actions in your summary."""

            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": conversation_history + [{"role": "user", "content": "Summarize the conversation."}],
                "system": system_prompt,
                "temperature": 0.93
            }
            
            self.logger.debug(f"Conversation summary API request: {json.dumps(request_body, indent=2)}")
            
            response = self.anthropic_client.messages.create(**request_body)
            summary = response.content[0].text if response.content else ""
            self.logger.info(f"Generated summary: {summary}")
            return summary

        except Exception as e:
            self.logger.error(f"Error in generating conversation summary: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return "The conversation ended without a clear summary."

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

    def summarize_full_conversation(self, actor1, actor2, conversation):
        try:
            self.logger.info(f"Summarizing conversation between {actor1.name} and {actor2.name}")
            system_prompt = f"""Summarize the conversation between {actor1.name} and {actor2.name} in a dungeon setting.
            Provide a single sentence summary of their conversation, focusing on the main topic or outcome."""

            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": conversation + [{"role": "user", "content": "Summarize the conversation."}],
                "system": system_prompt,
                "temperature": 0.93
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            summary = response.content[0].text if response.content else ""
            self.logger.info(f"Generated summary: {summary}")
            return summary

        except Exception as e:
            self.logger.error(f"Error in summarizing full conversation: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return "The conversation ended without a clear summary."

    def process_dialogue(self, speaker, listener, dialogue):
        # Define a neutral whitelist for names, titles, and fantasy terms
        neutral_whitelist = ["the destroyer", "the enigma", "the sage", "shadows", "age of shadows", "destiny", "dance"]
        
        # Add character names to the neutral whitelist
        for card in character_cards.values():
            neutral_whitelist.append(card['name'].lower())
        
        # Remove whitelisted words from the dialogue for sentiment analysis
        sanitized_dialogue = dialogue.lower()
        for word in neutral_whitelist:
            sanitized_dialogue = sanitized_dialogue.replace(word, "")
        
        sentiment_analyzer = SentimentIntensityAnalyzer()
        sentiment_scores = sentiment_analyzer.polarity_scores(sanitized_dialogue)
        compound_score = sentiment_scores['compound']

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

        # Adjust the relationship change based on the average sentiment
        if avg_sentiment < -0.5:
            relationship_change = -0.1
        elif avg_sentiment < -0.2:
            relationship_change = -0.05
        elif avg_sentiment < 0.2:
            relationship_change = 0
        elif avg_sentiment < 0.5:
            relationship_change = 0.05
        else:
            relationship_change = 0.1

        # Apply a context modifier
        context_modifier = 1.0
        if "apology" in dialogue.lower() or "sorry" in dialogue.lower():
            context_modifier = 0.5  # Reduce negative impact for apologies
        elif "thank" in dialogue.lower() or "appreciate" in dialogue.lower():
            context_modifier = 1.5  # Increase positive impact for gratitude

        relationship_change *= context_modifier

        # Update emotional state with increased sensitivity to negative interactions
        if compound_score > 0.1:
            listener_component.emotional_state = EmotionalState.HAPPY
            listener_component.emotional_intensity = min(1.0, listener_component.emotional_intensity + abs(compound_score) * 0.2)
        elif compound_score < -0.05:  # Lowered threshold for negative emotions
            listener_component.emotional_state = EmotionalState.ANGRY
            listener_component.emotional_intensity = min(1.0, listener_component.emotional_intensity + abs(compound_score) * 0.3)  # Increased intensity for negative emotions
        else:
            listener_component.emotional_intensity = max(0.0, listener_component.emotional_intensity - 0.05)

        # Update relationship
        listener.knowledge.update_relationship(speaker.name, relationship_change)
        speaker.knowledge.update_relationship(listener.name, relationship_change)

        # Check for aggression trigger with lower threshold
        if listener_component.emotional_state == EmotionalState.ANGRY and listener_component.emotional_intensity > 0.6:  # Lowered from 0.8
            if listener.knowledge.relationships[speaker.name] < -10:  # Lowered from -15
                self.trigger_aggression(listener, speaker)

        # Log relationship change (for debugging purposes)
        new_relationship_value = listener.knowledge.relationships[speaker.name]
        self.logger.debug(f"{listener.name}'s relationship with {speaker.name} changed by {relationship_change:.2f}. New value: {new_relationship_value:.2f}")

        # Return the relationship change for use in dialogue generation
        return relationship_change

    def map_sentiment_to_relationship(self, sentiment):
        max_change = 2  # Reduced max change for more gradual relationship shifts
        if sentiment > 0:
            change = min(int((sentiment ** 0.5) * 2.5), max_change)
        else:
            change = max(int(-((-sentiment) ** 0.5) * 2.5), -max_change)
        return change

    def trigger_aggression(self, aggressor, target):
        if isinstance(target, Actor) and not target.aggressive:
            target.become_aggressive(aggressor)
            self.logger.info(f"{aggressor.name} triggered aggression in {target.name}")
            self.game.show_message(f"{target.name} becomes aggressive towards {aggressor.name}!", MessageChannel.DIALOGUE)

    def attempt_to_calm(self, actor, target):
        if isinstance(target, Actor) and target.aggressive:
            # You can implement logic here to determine if the calming attempt is successful
            # For now, let's assume it always works
            target.calm_down()
            self.logger.info(f"{actor.name} attempted to calm {target.name}")
            self.game.show_message(f"{actor.name} successfully calms down {target.name}.", MessageChannel.DIALOGUE)

    def adjust_relationship_from_summary(self, actor1, actor2, summary):
        sentiment_analyzer = SentimentIntensityAnalyzer()
        sentiment_scores = sentiment_analyzer.polarity_scores(summary)
        compound_score = sentiment_scores['compound']

        # Map the sentiment score to a relationship change
        relationship_change = round(compound_score * 0.2, 1)  # Increased impact for overall conversation

        # Log initial relationship values
        initial_relationship1 = round(actor1.knowledge.relationships.get(actor2.name, 0), 1)
        initial_relationship2 = round(actor2.knowledge.relationships.get(actor1.name, 0), 1)
        self.logger.info(f"Initial relationship values - {actor1.name} to {actor2.name}: {initial_relationship1}, {actor2.name} to {actor1.name}: {initial_relationship2}")

        # Update relationships for both actors
        actor1.knowledge.update_relationship(actor2.name, relationship_change)
        actor2.knowledge.update_relationship(actor1.name, relationship_change)

        # Log new relationship values
        new_relationship1 = round(actor1.knowledge.relationships.get(actor2.name, 0), 1)
        new_relationship2 = round(actor2.knowledge.relationships.get(actor1.name, 0), 1)
        self.logger.info(f"Relationship between {actor1.name} and {actor2.name} changed by {relationship_change:.1f} based on conversation summary")
        self.logger.info(f"New relationship values - {actor1.name} to {actor2.name}: {new_relationship1:.1f}, {actor2.name} to {actor1.name}: {new_relationship2:.1f}")

        # Categorize the conversation based on the relationship change
        if relationship_change <= -0.2:
            conversation_quality = "terrible"
            message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, severely damaging their relationship."
        elif -0.1 <= relationship_change < 0:
            conversation_quality = "bad"
            message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, negatively affecting their relationship."
        elif relationship_change == 0:
            conversation_quality = "average"
            message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, with no significant impact on their relationship."
        elif 0 < relationship_change <= 0.1:
            conversation_quality = "good"
            message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, positively affecting their relationship."
        else:  # relationship_change >= 0.2
            conversation_quality = "great"
            message = f"The conversation between {actor1.name} and {actor2.name} was {conversation_quality}, significantly improving their relationship."

        # Show the categorized relationship change in the message log
        self.game.show_message(message, MessageChannel.SYSTEM)

    def show_dialogue(self, speaker, message):
        formatted_message = f"\n{speaker.name}: \"{message}\"\n"
        self.game.show_message(formatted_message, MessageChannel.DIALOGUE, sender=speaker)
