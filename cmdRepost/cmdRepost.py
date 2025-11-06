from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
import os
import time
import json
import re
import math

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
            'tps': self.ask_tps,
            'time': self.ask_time,
            # 'restart': self.restart_request,
            'here': self.broadcast_pos,
        }

        self.tp_log = {}

        # queue
        self.repost_remained = []
        self.repost_receiver = []
        self.player_pos_map = {}

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
        if len(self.repost_remained) > 0:
            remain = self.repost_remained[0]
            if remain > 0:
                self.logger.debug('CmdReposter.repost_remained = {:d}'.format(remain))
                match_obj_1 = re.match(r'[^<>]*?\[Server thread/INFO\].*?: ([^<>]*)$', line)
                if match_obj_1:
                    self.utils.tell(self.repost_receiver[0], match_obj_1.group(1))
                    self.repost_remained[0] -= 1
            else:
                del self.repost_remained[0]
                del self.repost_receiver[0]
                self.check_repost(line)

    def check_player_nbt(self, line):
        match_obj_1 = re.match(r'[^<>]*?\[Server thread/INFO\].*?: (.*)$', line)
        text = match_obj_1.group(1) if match_obj_1 else ''
        match_obj_2 = re.match(r'^(\w+) has the following entity data: (.*)$', text)
        if match_obj_2:
            # got player entity data
            player = match_obj_2.group(1)
            if player not in self.player_pos_map:
                return
            match_obj_pos = re.match(r'\[(.*?)d, (.*?)d, (.*?)d\]', match_obj_2.group(2))
            match_obj_dim = re.match(r'"(minecraft:\w+)"', match_obj_2.group(2))
            player_nbt = self.player_pos_map[player]
            if match_obj_pos:
                player_nbt['pos'] = (
                    math.floor(float(match_obj_pos.group(1)) + 0.5),  # x
                    math.ceil(float(match_obj_pos.group(2))),         # y
                    math.floor(float(match_obj_pos.group(3)) + 0.5),  # z
                )
                self.logger.debug('CmdReposter parsed player Pos data: {}'.format(player_nbt['pos']))
            if match_obj_dim:
                player_nbt['dim'] = match_obj_dim.group(1)
                self.logger.debug('CmdReposter parsed player Dimension data: {}'.format(player_nbt['dim']))
            if player_nbt['pos'] is not None and player_nbt['dim'] is not None:
                x, y, z = player_nbt['pos']
                dim = player_nbt['dim']
                output_string = f'[x:{x}, y:{y}, z:{z}, dim:{dim}]'
                cmd = f'execute as {player} run say {output_string}'
                self.logger.debug('CmdReposter generated position broadcast: {}'.format(output_string))
                self.core.write_server(cmd)
                del self.player_pos_map[player]

    @QtCore.pyqtSlot(list)
    def on_server_output(self, lines):
        for line in lines:
            self.check_tp(line)
            self.check_repost(line)
            self.check_player_nbt(line)

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
                self.repost_remained.append(4)  # repost the next messages to player
                self.repost_receiver.append('@a')  # repost to all players
        else:
            self.utils.tell(player, 'Command not acceptable. Please check again.')

    def ask_time(self, player, text_list):
        self.logger.debug('CmdReposter.ask_time called')

        # we only allow requesting for daytime by "!time"
        # so len(text_list) must equal to 1
        if len(text_list) == 1:
            self.core.write_server('/time query daytime')
            self.repost_remained.append(1)
            self.repost_receiver.append(player)
        else:
            self.utils.tell(player, 'Command not acceptable. Please check again.')

    def broadcast_pos(self, player, text_list):
        self.logger.debug('CmdReposter.broadcast_pos called')
        player = str(player)
        self.player_pos_map[player] = { 'pos': None, 'dim': None }
        # Reference (CN): https://zh.minecraft.wiki/w/%E5%91%BD%E4%BB%A4/data
        self.core.write_server(f'data get entity {player} Pos')
        self.core.write_server(f'data get entity {player} Dimension')
        # Wait for `check_player_nbt`
