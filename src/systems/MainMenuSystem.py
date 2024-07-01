import tcod
from tcod import libtcodpy
from tcod.event import KeySym

class MainMenuSystem:
    def __init__(self, game):
        self.game = game

    def show_main_menu(self):
        options = ['New Game', 'Load Game', 'Quit']
        selected = 0

        while True:
            self.game.root_console.clear()
            self.game.root_console.print(self.game.width // 2, self.game.height // 2 - 4, 'SANGUINE HOST', alignment=libtcodpy.CENTER)
            
            for i, option in enumerate(options):
                color = (255, 255, 255) if i == selected else (100, 100, 100)
                self.game.root_console.print(self.game.width // 2, self.game.height // 2 + i, option, fg=color, alignment=libtcodpy.CENTER)

            self.game.context.present(self.game.root_console)

            for event in tcod.event.wait():
                if event.type == "QUIT":
                    raise SystemExit()
                elif event.type == "KEYDOWN":
                    if event.sym == KeySym.UP:
                        selected = (selected - 1) % len(options)
                    elif event.sym == KeySym.DOWN:
                        selected = (selected + 1) % len(options)
                    elif event.sym == KeySym.RETURN:
                        return options[selected]

    def handle_main_menu(self):
        choice = self.show_main_menu()
        if choice == 'New Game':
            self.game.new_game()
        elif choice == 'Load Game':
            self.game.load_game()
        elif choice == 'Quit':
            raise SystemExit()