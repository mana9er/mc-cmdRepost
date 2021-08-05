from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
import os
import time
import json
import re

__all__ = ['CmdReposter']


class CmdReposter(QtCore.QObject):
    cmd_prefix = '!'

    def __init__(self, logger, core, config_file):
        super(CmdReposter, self).__init__(core)
        self.core = core
        self.logger = logger
        self.disabled = False

        # load config
        self.configs = {}
        if os.path.exists(config_file):
            self.logger.info('Loading configs...')
            with open(config_file, 'r', encoding='utf-8') as cf:
                self.configs = json.load(cf)
        else:
            self.logger.warning('config.json not found. Using default settings.')

        # load mcBasicLib
        self.utils = core.get_plugin('mcBasicLib')
        if self.utils is None:
            self.logger.error('Failed to load plugin "mcBasicLib", cmdRepost will be disabled.')
            self.logger.error('Please make sure that "mcBasicLib" has been added to plugins.')
            self.disabled = True

        if self.disabled:
            return
        
        # connect signals and slots
        self.utils.sig_input.connect(self.on_player_input)
        self.core.sig_server_output.connect(self.on_server_output)
        self.core.sig_server_stop.connect(self.on_server_stop)

        # available commands
        self.cmd_available = {
            'tp': self.tp_request,
            # TODO: tphere
            'tps': self.ask_tps,
            'time': self.ask_time,
            'restart': self.restart_request,
        }

        self.tp_log = {}

        self.repost_remained = 0
        self.repost_receiver = None

        self.timer = QTimer(self)

    def check_tp(self, line):
        match_obj_1 = re.match(r'[^<>]*?\[Server thread/INFO\].*?: (.*)$', line)
        text = match_obj_1.group(1) if match_obj_1 else ''
        match_obj_2 = re.match(r'^Teleported (\w+)', text)
        if match_obj_2:
            # someone has been teleported
            player = match_obj_2.group(1)
            self.logger.debug('CmdReposter.check_tp found player {} teleported'.format(player))
            # repost messages to the player
            self.core.write_server('/tellraw {} {}'.format(player, json.dumps({'text': text, 'color': 'yellow'})))
            self.tp_log[player] = time.time()  # record latest teleported time

    def check_repost(self, line):
        if self.repost_remained > 0:
            self.logger.debug('CmdReposter.repost_remained = {:d}'.format(self.repost_remained))
            match_obj_1 = re.match(r'[^<>]*?\[Server thread/INFO\].*?: ([^<>]*)$', line)
            if match_obj_1:
                self.utils.tell(self.repost_receiver, match_obj_1.group(1))
                self.repost_remained -= 1

    @QtCore.pyqtSlot(list)
    def on_server_output(self, lines):
        for line in lines:
            self.check_tp(line)
            self.check_repost(line)

    @QtCore.pyqtSlot(tuple)
    def on_player_input(self, pair):
        self.logger.debug('CmdReposter.on_player_input called')
        player, text = pair
        text_list = text.split()

        if len(text) == 0:
            return
        
        for cmd in self.cmd_available:
            if text_list[0] == self.cmd_prefix + cmd:
                self.cmd_available[cmd](player, text_list)
                break

    @QtCore.pyqtSlot()
    def on_server_stop(self):
        self.logger.debug('CmdReposter.on_server_stop called')
        self.tp_log.clear()  # clear all tp records

    def tp_request(self, player, text_list):
        self.logger.debug('CmdReposter.tp_request called')

        if player.is_console():
            return

        if player.name not in self.tp_log:
            self.tp_log[player.name] = 0

        tp_cd = 0  # default setting
        if 'tp-cd' in self.configs:
            tp_cd = self.configs['tp-cd']

        # checking cool-down-time
        cur_time = time.time()
        if cur_time - self.tp_log[player.name] < tp_cd:
            remain_sec = tp_cd - (cur_time - self.tp_log[player.name])
            self.utils.tell(player, 'Command tp is now cooling down!')
            self.utils.tell(player, 'You cannot use tp again until {:d} seconds later.'.format(int(remain_sec)))
            return

        args = text_list[1:]
        tp_cmd = '/execute as {} at {} run tp {} '.format(player.name, player.name, player.name)
        if len(args) == 1:
            # tp to player
            self.core.write_server(tp_cmd + args[0])
        elif len(args) == 3:
            # tp to coordinate
            self.core.write_server(tp_cmd + '{} {} {}'.format(args[0], args[1], args[2]))
        else:
            self.utils.tell(player, 'Command not acceptable. Please check again.')

    def ask_tps(self, player, text_list):
        self.logger.debug('CmdReposter.ask_tps called')
        
        if len(text_list) == 1:
            if 'forge' not in self.configs or not self.configs['forge']:
                return
            else:
                self.core.write_server('/forge tps')
                self.repost_remained = 4  # repost the next messages to player
                self.repost_receiver = player
        else:
            self.utils.tell(player, 'Command not acceptable. Please check again.')

    def ask_time(self, player, text_list):
        self.logger.debug('CmdReposter.ask_time called')

        # we only allow requesting for daytime by "!time"
        # so len(text_list) must equal to 1
        if len(text_list) == 1:
            self.core.write_server('/time query daytime')
            self.repost_remained = 1
            self.repost_receiver = player
        else:
            self.utils.tell(player, 'Command not acceptable. Please check again.')

    def restart_request(self, player, text_list):
        pass
