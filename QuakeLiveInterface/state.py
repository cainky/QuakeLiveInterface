import json
import logging

logger = logging.getLogger(__name__)


class Player:
    """Represents a player in the game."""
    def __init__(self, steam_id, name, health, armor, position, velocity, view_angles, is_alive, weapons, selected_weapon):
        self.steam_id = steam_id
        self.name = name
        self.health = health
        self.armor = armor
        self.position = position
        self.velocity = velocity
        self.view_angles = view_angles
        self.is_alive = is_alive
        self.weapons = weapons
        self.selected_weapon = selected_weapon


class Weapon:
    """Represents a weapon in the game."""
    def __init__(self, name, ammo):
        self.name = name
        self.ammo = ammo


class Item:
    """Represents an item on the map."""
    def __init__(self, name, position, spawn_time, is_available):
        self.name = name
        self.position = position
        self.spawn_time = spawn_time
        self.is_available = is_available


class GameState:
    """
    Represents the state of the game at a particular moment.
    This class is updated from data received from the minqlx plugin via Redis.
    """

    def __init__(self):
        self.agent = None
        self.opponents = []
        self.items = []
        self.game_in_progress = False
        self.game_type = None
        self.map_name = None
        self.map_geometry = None  # This will be loaded once per map

    def update_from_redis(self, redis_data: str):
        """
        Updates the game state from a JSON string received from Redis.
        Args:
            redis_data: A JSON string containing the game state.
        """
        try:
            data = json.loads(redis_data)

            # Update agent state
            agent_data = data.get('agent')
            if agent_data:
                self.agent = self._create_player_from_data(agent_data)

            # Update opponents
            self.opponents = [self._create_player_from_data(p) for p in data.get('opponents', [])]

            # Update items
            self.items = [self._create_item_from_data(i) for i in data.get('items', [])]

            self.game_in_progress = data.get('game_in_progress')
            self.game_type = data.get('game_type')
            self.map_name = data.get('map_name')

            # Map geometry is loaded separately
            if 'map_geometry' in data:
                self.map_geometry = data.get('map_geometry')

            logger.debug("Game state updated from Redis data.")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from Redis: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing key in game state data from Redis: {e}")
            raise

    def _create_player_from_data(self, player_data):
        weapons = [Weapon(w['name'], w['ammo']) for w in player_data.get('weapons', [])]
        selected_weapon = Weapon(player_data['selected_weapon']['name'], player_data['selected_weapon']['ammo']) if player_data.get('selected_weapon') else None
        return Player(
            steam_id=player_data.get('steam_id'),
            name=player_data.get('name'),
            health=player_data.get('health'),
            armor=player_data.get('armor'),
            position=player_data.get('position'),
            velocity=player_data.get('velocity'),
            view_angles=player_data.get('view_angles', {'pitch': 0, 'yaw': 0, 'roll': 0}),
            is_alive=player_data.get('is_alive'),
            weapons=weapons,
            selected_weapon=selected_weapon
        )

    def _create_item_from_data(self, item_data):
        return Item(
            name=item_data.get('name'),
            position=item_data.get('position'),
            spawn_time=item_data.get('spawn_time'),
            is_available=item_data.get('is_available')
        )

    def get_agent(self):
        return self.agent

    def get_opponents(self):
        return self.opponents

    def get_items(self):
        return self.items
