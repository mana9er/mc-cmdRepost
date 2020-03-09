from .cmdRepost import CmdReposter

instance = None


def load(logger, core):
    # Function "load" is required by mana9er-core.
    from os import path
    config_file = path.join(core.init_cwd, 'cmdRepost', 'config.json')
    CmdReposter(logger, core, config_file)
