character_cards = {
    "wise_old_man": {
        "name": "Eldric the Sage",
        "appearance": "An elderly man with a long white beard, wearing tattered robes adorned with mystical symbols.",
        "personality": "Wise, patient, and slightly cryptic. Speaks in riddles and metaphors.",
        "background": "Eldric has lived in the dungeon for centuries, observing its changes and guarding ancient secrets.",
        "knowledge": "Extensive knowledge of the dungeon's history, magical artifacts, and the creatures that inhabit it.",
        "goals": "To guide worthy adventurers and preserve the balance of power within the dungeon.",
        "speech_style": "Uses archaic language and often refers to historical or mythological events.",
        "health": 30,
        "defense": 2,
        "power": 5,
        "aggression_type": "peaceful",
        "target_preference": ["none"]
    },
    "mysterious_stranger": {
        "name": "Lyra the Enigma",
        "appearance": "A cloaked figure with piercing silver eyes, face partially obscured by a shadowy hood.",
        "personality": "Mysterious, alluring, and unpredictable. Speaks in cryptic phrases and riddles.",
        "background": "Lyra's origins are unknown, but she seems to appear wherever intrigue and danger intersect.",
        "knowledge": "Possesses uncanny insight into the hidden workings of the dungeon and its inhabitants.",
        "goals": "To manipulate events from the shadows and test the worthiness of adventurers.",
        "speech_style": "Uses poetic language filled with double meanings and veiled warnings.",
        "health": 30,
        "defense": 2,
        "power": 5,
        "aggression_type": "neutral",
        "target_preference": ["threats"]
    },
    "aggressive_monster": {
        "name": "Grunk the Destroyer",
        "appearance": "A hulking, red-skinned brute with glowing yellow eyes and sharp claws.",
        "personality": "Aggressive, single-minded, and always looking for a fight.",
        "background": "Grunk was created by dark magic to be a relentless hunter and destroyer.",
        "knowledge": "Limited to basic combat tactics and tracking prey.",
        "goals": "To destroy any intruders in its territory, especially the player.",
        "speech_style": "Grunts, roars, and simple, aggressive phrases.",
        "health": 30,
        "defense": 2,
        "power": 5,
        "aggression_type": "hostile",
        "target_preference": ["player", "other_actors"]
    }
}

def get_character_card(key, default=None):
    if isinstance(key, dict):
        return key
    card = character_cards.get(key, default)
    if card and hasattr(card, 'get'):
        card['current_position'] = f"({card.get('x', '?')}, {card.get('y', '?')})"
    return card

def set_character_card(key, value):
    character_cards[key] = value
