import json
import logging

logger = logging.getLogger(__name__)


class GameState:
    """
    Represents the state of the game at a particular moment.
    This class is updated from data received from the minqlx plugin via Redis.
    """

    def __init__(self):
        self.player_id = None
        self.health = 0
        self.armor = 0
        self.position = {'x': 0, 'y': 0, 'z': 0}
        self.ammo = {}
        self.opponents = []
        self.game_in_progress = False
        self.game_type = None

    def update_from_redis(self, redis_data: str):
        """
        Updates the game state from a JSON string received from Redis.
        Args:
            redis_data: A JSON string containing the game state.
        """
        try:
            data = json.loads(redis_data)
            self.player_id = data.get('player_id')
            self.health = data.get('health')
            self.armor = data.get('armor')
            self.position = data.get('position')
            self.ammo = data.get('ammo')
            self.opponents = data.get('opponents')
            self.game_in_progress = data.get('game_in_progress')
            self.game_type = data.get('game_type')
            logger.debug("Game state updated from Redis data.")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from Redis: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing key in game state data from Redis: {e}")
            raise

    def get_player_position(self):
        return self.position

    def get_player_health(self):
        return self.health

    def get_player_armor(self):
        return self.armor

    def get_player_ammo(self):
        return self.ammo

    def get_opponents(self):
        return self.opponents
