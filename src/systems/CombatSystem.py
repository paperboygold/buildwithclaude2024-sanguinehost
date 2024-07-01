from ecs.ecs import System
from components.FighterComponent import FighterComponent
from systems.MessageSystem import MessageChannel
from entities.Actor import Actor
from components.ActorComponent import ActorComponent, ActorState

class CombatSystem(System):
    def __init__(self, game):
        self.game = game

    def attack(self, attacker, target):
        attacker_fighter = attacker.get_component(FighterComponent)
        target_fighter = target.get_component(FighterComponent)

        damage = attacker_fighter.power - target_fighter.defense

        if damage > 0:
            target_fighter.hp -= damage
            self.game.show_message(
                f"{attacker.name.capitalize()} attacks {target.name} for {damage} hit points.",
                MessageChannel.COMBAT
            )
            if not target.aggressive and isinstance(target, Actor):
                target.get_component(ActorComponent).state = ActorState.AGGRESSIVE
                target.get_component(ActorComponent).aggressor = attacker
                self.game.show_message(f"{target.name} becomes aggressive!", MessageChannel.COMBAT)

            if target_fighter.hp <= 0:
                self.kill(target)
                attacker_component = attacker.get_component(ActorComponent)
                if attacker_component and attacker_component.aggressor == target:
                    attacker_component.state = ActorState.IDLE
                    attacker_component.aggressor = None
                    self.game.show_message(f"{attacker.name} calms down.", MessageChannel.COMBAT)
        else:
            self.game.show_message(
                f"{attacker.name.capitalize()} attacks {target.name} but does no damage.",
                MessageChannel.COMBAT
            )

    def kill(self, target):
        self.game.show_message(f"{target.name.capitalize()} is defeated!", MessageChannel.COMBAT)
        if target == self.game.world.player:
            self.game.show_message("Game Over! Press any key to return to the main menu.", MessageChannel.SYSTEM)
            self.game.game_over = True
        else:
            self.game.world.entities.remove(target)