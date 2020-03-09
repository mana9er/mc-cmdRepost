from PyQt5 import QtCore
import os
import time
import json

__all__ = ['CmdReposter']


class CmdReposter(QtCore.QObject):
    cmd_prefix = '!'

    def __init__(self, logger, core, config_file):
        super(CmdReposter, self).__init__(core)
        self.core = core
        self.logger = logger

        # load config
        self.configs = {}
        if os.path.exists(config_file):
            self.logger.info('Loading configs...')
            with open(config_file, 'r', encoding='utf-8') as cf:
                self.configs = json.load(cf)
        else:
            self.logger.warning('config.json not found. Using default settings.')

        # connect signals and slots
        self.core.notifier.sig_input.connect(self.on_player_input)

        # available commands
        self.cmd_available = {
            'tp': self.tp_request,
            # TODO: tphere
            'tps': self.ask_tps,
        }

    def server_say(self, text):
        self.core.write_server('/say {}'.format(text))

    def server_tell(self, player, text):
        self.core.write_server('/tellraw {} {}'.format(player.name, json.dumps({'text': text, 'color': 'yellow'})))

    def server_warn(self, player, text):
        self.core.write_server('/tellraw {} {}'.format(player.name, json.dumps({'text': text, 'color': 'red'})))

    def on_player_input(self, pair):
        self.logger.debug('CmdReposter.on_player_input called')
        player = pair[0]
        text = pair[1]
        text_list = text.split()

        if player.is_console():
            return
        
        for cmd in self.cmd_available:
            if text_list[0] == self.cmd_prefix + cmd:
                try:
                    self.cmd_available[cmd](player, text_list)
                except AttributeError:
                    self.logger.error('Fatal: AttributeError raised.')
                    self.server_warn(player, 'cmdRepost internal error raised.')
                except KeyError:
                    self.logger.error('Fatal: KeyError raised.')
                    self.server_warn(player, 'cmdRepost internal error raised.')
                
                break

    def tp_request(self, player, text_list):
        self.logger.debug('CmdReposter.tp_request called')

        if not self.tp_log:
            self.tp_log = {}
        if player.name not in self.tp_log:
            self.tp_log[player.name] = 0

        tp_cd = 0  # default setting
        if 'tp-cd' in self.configs:
            tp_cd = self.configs['tp-cd']

        # checking cool-down-time
        cur_time = time.time()
        if cur_time - self.tp_log[player.name] < tp_cd:
            remain_sec = tp_cd - (cur_time - self.tp_log[player.name])
            self.server_tell(player, 'You cannot use tp again until {} seconds later.'.format(str(remain_sec)))
            return
        else:
            self.tp_log[player.name] = cur_time

        args = text_list[1:]
        tp_cmd = '/execute as {} at {} run tp {} '.format(player.name, player.name, player.name)
        if len(args) == 1:
            # tp to player
            self.core.write_server(tp_cmd + args[0])
        elif len(args) == 3:
            # tp to coordinate
            self.core.write_server(tp_cmd + '{} {} {}'.format(args[0], args[1], args[2]))
        else:
            self.server_tell(player, 'Command not acceptable. Please check again.')

    def ask_tps(self, player, text_list):
        self.logger.debug('CmdReposter.log_tps called')
        if len(text_list) == 1:
            if 'forge' not in self.configs or not self.configs['forge']:
                return
            else:
                self.core.write_server('/forge tps')
        else:
            self.server_tell(player, 'Command not acceptable. Please check again.')


