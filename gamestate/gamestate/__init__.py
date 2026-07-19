from ._gamestate import *  # noqa: F403
from .builders import StateBuilders

for name, func in StateBuilders.__dict__.items():
    if name.startswith("__"):
        continue
    # `property` objects aren't callable themselves (only their fget/fset
    # are), so they need to be special-cased here to still get patched onto
    # GameState -- setattr on a class with a property object works fine
    # since it's just a class attribute (the descriptor protocol handles
    # the rest on instance attribute access).
    if callable(func) or isinstance(func, property):
        setattr(GameState, name, func)  # noqa: F405
