# Sanguine Host: An AI-Powered Roguelike Adventure

## Overview

Sanguine Host is an innovative roguelike game that showcases the power of Claude 3.5 in creating immersive roleplay experiences. Developed for the [Build with Claude contest](https://docs.anthropic.com/en/build-with-claude-contest/overview), this project demonstrates how advanced language models can enhance gaming interactions, even in simple environments.

## Features

- **AI-Driven NPCs**: Interact with non-player characters powered by Claude 3.5, capable of engaging in natural, context-aware dialogues.
- **Dynamic Storytelling**: Experience a unique adventure each time you play, with AI-generated narratives and character responses.
- **Classic Roguelike Gameplay**: Navigate through a text-based world, encounter challenges, and make decisions that impact your journey.

## How It Works

Sanguine Host utilizes the Anthropic API to integrate Claude 3.5 into the game's dialogue system. When players interact with NPCs, the game sends the conversation context to Claude, which then generates appropriate responses based on the character's personality and the game's setting.

Key components:
1. **Game Engine**: Built using Python and the tcod library for roguelike functionality.
2. **AI Integration**: Anthropic's API is used to communicate with Claude 3.5 for NPC dialogues.
3. **Dynamic Messaging System**: Handles various types of in-game messages and renders them appropriately.

## Getting Started

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up your Anthropic API key in a `.env` file:
   ```
   ANTHROPIC_API_KEY=your_api_key_here
   ```
4. Run the game:
   ```
   python main.py
   ```

## Controls

- Arrow keys: Move the player
- 'i': Interact with adjacent NPCs
- '.': Wait a turn
- 'q': Quit the game

## Why This Matters

Sanguine Host demonstrates that even with minimal graphical elements, AI can significantly enhance the depth and immersion of gaming experiences. By leveraging Claude 3.5's natural language processing capabilities, we've created NPCs that can engage in meaningful, context-aware conversations, making each playthrough unique and engaging.

This project serves as a proof of concept for how AI can be integrated into various gaming genres, potentially revolutionizing narrative-driven games, RPGs, and interactive fiction.

## Future Enhancements

- Expand the game world with more diverse NPCs and locations
- Implement a quest system with AI-generated objectives
- Add character progression and inventory management
- Explore multi-turn dialogue strategies for more complex interactions

## Contributing

We welcome contributions to Sanguine Host! Whether it's bug fixes, new features, or improvements to the AI integration, please feel free to submit pull requests or open issues for discussion.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Anthropic for providing access to Claude 3.5
- The tcod library developers for their excellent roguelike toolkit
