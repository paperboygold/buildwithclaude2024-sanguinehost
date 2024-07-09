import logging
import json
import time
import random
import traceback
from systems.MessageSystem import MessageChannel
from components.ActorComponent import ActorComponent, ActorState

class ConversationManager:
    def __init__(self, game, anthropic_client):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.anthropic_client = anthropic_client

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
                    choice = self.game.dialogue_system.get_player_choice(f"{actor1.name} and {actor2.name} are about to have a conversation. Do you want to listen?")
                    if choice:
                        self.game.show_message(f"{actor1.name} and {actor2.name} have started a conversation.", MessageChannel.DIALOGUE, sender=actor1)
                    else:
                        summary, conversation_history = self.summarize_conversation(actor1, actor2)
                        if summary:  # Check if summary is not None
                            self.game.dialogue_system.add_conversation_memory(actor1, actor2, summary)
                            self.game.dialogue_system.adjust_relationship_from_summary(actor1, actor2, conversation_history, summary)
                        else:
                            self.logger.error(f"Failed to generate summary for conversation between {actor1.name} and {actor2.name}")
                        return
                else:
                    summary, conversation_history = self.summarize_conversation(actor1, actor2)
                    if summary:  # Check if summary is not None
                        self.game.dialogue_system.add_conversation_memory(actor1, actor2, summary)
                        self.game.dialogue_system.adjust_relationship_from_summary(actor1, actor2, conversation_history, summary)
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
                    self.game.dialogue_system.show_dialogue(actor1, actor_response)

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
                conversation_history = [
                    {"role": "system", "content": "A simulated conversation occurred."},
                    {"role": "assistant", "content": summary}
                ]
                return summary, conversation_history
            else:
                self.logger.error("Failed to generate conversation summary: Empty response")
                return None, None

        except Exception as e:
            self.logger.error(f"Error in summarizing conversation: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return None, None

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
                    self.game.dialogue_system.show_dialogue(current_actor, actor_response)

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
        self.game.dialogue_system.add_conversation_memory(actor1, actor2, summary)
        self.game.dialogue_system.adjust_relationship_from_summary(actor1, actor2, conversation_history, summary)
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