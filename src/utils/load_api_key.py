import os
import logging
from dotenv import load_dotenv
from typing import Optional

def load_api_key() -> Optional[str]:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logging.warning("ANTHROPIC_API_KEY not found in .env file.")
        print("Please enter your Anthropic API key manually:")
        api_key = input().strip()
    return api_key