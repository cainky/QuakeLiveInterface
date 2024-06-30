from enum import Enum, auto

class CommandType(Enum):
    MOVE = auto()
    AIM = auto()
    WEAPON = auto()
    FIRE = auto()
    JUMP = auto()
    SAY = auto()

class Direction(Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"

class WeaponId(Enum):
    GAUNTLET = 1
    MACHINEGUN = 2
    SHOTGUN = 3
    GRENADE_LAUNCHER = 4
    ROCKET_LAUNCHER = 5
    LIGHTNING_GUN = 6
    RAILGUN = 7
    PLASMA_GUN = 8
    BFG = 9

# Add other constants as needed
DEFAULT_PORT = 27960
STATE_REQUEST = b"get_state"
COMMAND_PREFIX = b"command:"