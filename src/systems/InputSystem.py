import tcod
from tcod.event import KeySym
from ecs.ecs import System
from systems.MessageSystem import MessageChannel

class InputSystem(System):
    def __init__(self, game):
        self.game = game

    def handle_input(self):
        for event in tcod.event.wait():
            if event.type == "QUIT":
                raise SystemExit()
            elif event.type == "KEYDOWN":
                return self.handle_keydown(event)
        return False

    def handle_keydown(self, event):
        action_taken = False
        if event.sym == KeySym.UP:
            self.game.move_player(0, -1)
            action_taken = True
        elif event.sym == KeySym.DOWN:
            self.game.move_player(0, 1)
            action_taken = True
        elif event.sym == KeySym.LEFT:
            self.game.move_player(-1, 0)
            action_taken = True
        elif event.sym == KeySym.RIGHT:
            self.game.move_player(1, 0)
            action_taken = True
        elif event.sym == KeySym.PERIOD:
            self.game.message_system.add_message("You wait for a moment.", MessageChannel.SYSTEM)
            action_taken = True
        elif event.sym == KeySym.i:
            self.game.interact()
        elif event.sym == KeySym.q:
            raise SystemExit()
        return action_taken