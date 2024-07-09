import logging
import json
import traceback
from systems.MessageSystem import MessageChannel
from components.ActorComponent import ActorComponent

class ConversationSummarizer:
    def __init__(self, game, anthropic_client):
        self.game = game
        self.anthropic_client = anthropic_client
        self.logger = logging.getLogger(__name__)

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