from .cmdRepost import CmdReposter

instance = None


def load(logger, core):
    # Function "load" is required by mana9er-core.
    instance = CmdReposter(logger, core)