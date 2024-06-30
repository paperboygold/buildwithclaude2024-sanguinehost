import logging
import tcod
import json
import time
import textwrap
import traceback
from systems.MessageSystem import MessageChannel, Message
from components.ActorComponent import ActorComponent
from tcod.event import KeySym

class DialogueSystem:
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(__name__)
        self.anthropic_client = game.anthropic_client

    def start_dialogue(self, actor):
        try:
            actor_component = actor.get_component(ActorComponent)
            self.logger.info(f"Starting dialogue with {actor.name}")
            self.logger.debug(f"Actor {actor.name} character card: {actor_component.character_card}")
            self.logger.debug(f"Actor {actor.name} knowledge: {actor.knowledge.get_summary()}")
            self.game.show_message(f"You are now talking to {actor.name}", MessageChannel.DIALOGUE, sender=actor)
            
            while True:
                user_input = self.get_user_input("You: ")
                if user_input is None:  # User pressed Escape
                    self.logger.info(f"Dialogue with {actor.name} ended by user")
                    self.game.show_message("Dialogue ended.", MessageChannel.DIALOGUE, (0, 255, 255))
                    break
            
                self.logger.debug(f"Processing user input: {user_input}")
                self.game.show_message(f"You: {user_input}", MessageChannel.DIALOGUE, (0, 255, 0))
            
                actor_component.dialogue_history.append({"role": "user", "content": user_input})
                
                try:
                    relationship_info = ""
                    if actor.knowledge.known_actors:
                        other_actor_name, relationship_data = next(iter(actor.knowledge.known_actors.items()))
                        relationship = relationship_data["relationship"]
                        relationship_story = relationship_data["story"]
                        relationship_info = f"You have a {relationship} relationship with {other_actor_name}. {relationship_story} "

                    system_prompt = f"""You are {actor.name}, an NPC in a roguelike game. Character: {actor_component.character_card}
Environmental knowledge: {actor.knowledge.get_summary()}
{relationship_info}Respond in character with extremely brief responses, typically 1-2 short sentences or 10 words or less. Be concise and direct.
Important: Speak only in dialogue. Do not describe actions, appearances, use asterisks or quotation marks. Simply respond with what your character would say."""
                    
                    self.logger.info(f"API Request for {actor.name}:")
                    self.logger.info(f"System Prompt: {system_prompt}")
                    self.logger.debug(f"Dialogue history: {json.dumps(actor_component.dialogue_history, indent=2)}")
                    
                    request_body = {
                        "model": "claude-3-5-sonnet-20240620",
                        "max_tokens": 50,
                        "messages": actor_component.dialogue_history,
                        "system": system_prompt,
                        "temperature": 0.7,
                        "top_p": 1,
                        "stream": False,
                        "stop_sequences": ["\n\nHuman:", "\n\nSystem:", "\n\nAssistant:"]
                    }
                    
                    response = self.anthropic_client.messages.create(**request_body)
                    
                    self.logger.info(f"API Response for {actor.name}:")
                    self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
                    
                    actor_response = response.content[0].text if response.content else ""
                    actor_component.dialogue_history.append({"role": "assistant", "content": actor_response})
                    
                    self.game.show_message(f"{actor.name}: {actor_response}", MessageChannel.DIALOGUE, sender=actor)
                except Exception as e:
                    self.logger.error(f"Error in AI response: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                    self.game.show_message(f"Error: Unable to get NPC response", MessageChannel.SYSTEM, (255, 0, 0))
        except Exception as e:
            self.logger.error(f"Error in dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.game.show_message(f"An error occurred during dialogue", MessageChannel.SYSTEM, (255, 0, 0))

    def start_actor_dialogue(self, actor1, actor2):
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            current_time = time.time()
            if current_time - actor1_component.last_conversation_time < actor1_component.conversation_cooldown or \
               current_time - actor2_component.last_conversation_time < actor2_component.conversation_cooldown:
                return  # Skip if either actor is on cooldown

            actor1_component.last_conversation_time = current_time
            actor2_component.last_conversation_time = current_time

            player_can_see = self.game.world.game_map.is_in_fov(int(self.game.world.player.x), int(self.game.world.player.y)) and \
                             (self.game.world.game_map.is_in_fov(int(actor1.x), int(actor1.y)) or 
                              self.game.world.game_map.is_in_fov(int(actor2.x), int(actor2.y)))

            if player_can_see:
                choice = self.get_player_choice(f"{actor1.name} and {actor2.name} are about to have a conversation. Do you want to listen?")
                if choice:
                    self.game.show_message(f"{actor1.name} and {actor2.name} have started a conversation.", MessageChannel.DIALOGUE, sender=actor1)
                else:
                    self.summarize_conversation(actor1, actor2)
                    return

            relationship_info = actor1.knowledge.get_relationship_story(actor2.name) or ""
             
            system_prompt = f"""You are simulating a conversation between {actor1.name} and {actor2.name} in a dungeon setting.
{actor1.name}'s character: {actor1_component.character_card}
{actor2.name}'s character: {actor2_component.character_card}
Their relationship: {relationship_info}
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
                "temperature": 0.7
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
                self.game.show_message(f"{actor1.name}: {actor_response}", MessageChannel.DIALOGUE, sender=actor1)

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

    def summarize_conversation(self, actor1, actor2):
        try:
            actor1_component = actor1.get_component(ActorComponent)
            actor2_component = actor2.get_component(ActorComponent)
            
            system_prompt = f"""Summarize a brief conversation between {actor1.name} and {actor2.name} in a dungeon setting.
            {actor1.name}'s character: {actor1_component.character_card}
            {actor2.name}'s character: {actor2_component.character_card}
            Their relationship: {actor1.knowledge.get_relationship_story(actor2.name) or ""}
            Environmental knowledge: {actor1.knowledge.get_summary()}
            Provide a single sentence summary of their conversation, focusing on the main topic or outcome."""

            request_body = {
                "model": "claude-3-5-sonnet-20240620",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Summarize the conversation."}],
                "system": system_prompt,
                "temperature": 0.9
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            summary = response.content[0].text if response.content else ""

            self.game.show_message(summary, MessageChannel.DIALOGUE)

        except Exception as e:
            self.logger.error(f"Error in summarizing conversation: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.game.show_message(f"An error occurred while summarizing the conversation", MessageChannel.SYSTEM, (255, 0, 0))

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

            self.logger.debug(f"Current speaker: {current_actor.name}, Responding to: {other_actor.name}")
            self.logger.debug(f"Conversation turns - {actor1.name}: {actor1_component.conversation_turns}, {actor2.name}: {actor2_component.conversation_turns}")

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
                "temperature": 0.7
            }
            
            response = self.anthropic_client.messages.create(**request_body)
            
            self.logger.info(f"API Response for {current_actor.name}:")
            self.logger.info(f"Response: {json.dumps(response.model_dump(), indent=2)}")
            
            actor_response = response.content[0].text if response.content else ""
            
            if actor_response.strip():  # Only add non-empty responses
                conversation.append({"role": "assistant", "content": actor_response})
                
                if player_can_see:
                    self.game.show_message(f"{current_actor.name}: {actor_response}", MessageChannel.DIALOGUE, sender=current_actor)

            # Update the conversation for both actors
            actor1_component.current_conversation = conversation
            actor2_component.current_conversation = conversation

            # Increment the conversation turn counter for the current actor
            current_actor.get_component(ActorComponent).conversation_turns += 1

        except Exception as e:
            self.logger.error(f"Error in continuing actor dialogue: {str(e)}")
            self.logger.debug(traceback.format_exc())
            if player_can_see:
                self.game.show_message(f"An error occurred during actor dialogue", MessageChannel.SYSTEM, (255, 0, 0))

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
        
        if player_can_see:
            self.game.show_message(f"{actor1.name} and {actor2.name} have ended their conversation.", MessageChannel.DIALOGUE)

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
