from .cmdRepost import CmdReposter

# list dependencies
dependencies = ['mcBasicLib']


def load(logger, core):
    # Function "load" is required by mana9er-core.
    from os import path
    config_file = path.join(core.root_dir, 'cmdRepost', 'config.json')
    return CmdReposter(logger, core, config_file)
