from PyQt5 import QtCore
import time

__all__ = ['CmdReposter']


class CmdReposter(QtCore.QObject):
    cmd_prefix = '!'

    def __init__(self, logger, core):
        super(CmdReposter, self).__init__()
        self.core = core
        self.logger = logger

        # connect signals and slots
        self.core.notifier.sig_input.connect(self.on_player_input)

        # available commands
        self.cmd_available = {
            'tp': self.tp_request,
        }

    def server_tell(self, player, text):
        self.core.write_server('/tellraw {} {}'.format(player.name, json.dumps({'text': text, 'color': 'yellow'})))

    def on_player_input(self, pair):
        self.logger.debug('CmdReposter.on_player_input called')
        player = pair[0]
        text = pair[1]
        text_list = text.split()

        if player.is_console():
            return
        
        for cmd in self.cmd_available:
            if text_list[0] == self.cmd_prefix + cmd:
                self.cmd_available[cmd](player, text_list)
                break

    def tp_request(self, player, text_list):
        self.logger.debug('CmdReposter.tp_request called')
        args = text_list[1:]
        if len(args) == 1:
            # tp to player
            self.core.write_server('/tp {} {}'.format(player.name, args[0]))
        elif len(args) == 3:
            # tp to coordinate
            self.core.write_server('/tp {} {} {} {}'.format(player.name, args[0], args[1], args[2]))
        else:
            self.server_tell(player, 'Command not acceptable. Please check again.')


