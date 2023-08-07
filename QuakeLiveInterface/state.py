import struct
from enum import Enum

class PacketType(Enum):
    PLAYER_MOVEMENT = 1
    ITEM_PICKUP = 2
    PLAYER_SHOT = 3
    PLAYER_DEATH = 4
    GAME_STATE_UPDATE = 5


class GameState:

    def __init__(self):
        self.player_positions = {}
        self.item_picked_by = {}
        self.player_ammo = {}
        self.player_health = {}

    def get_packet_type(self, data_packet: bytes) -> PacketType:
        header = struct.unpack('B', data_packet[:1])[0]  # Extract the header byte
        return PacketType(header)

    def update(self, data_packet: bytes):
        packet_type = self.get_packet_type(data_packet)
        
        if packet_type == PacketType.PLAYER_MOVEMENT:
            self.handle_player_movement(data_packet)
        elif packet_type == PacketType.ITEM_PICKUP:
            self.handle_item_pickup(data_packet)
        elif packet_type == PacketType.PLAYER_SHOT:
            self.handle_player_shot(data_packet)
        elif packet_type == PacketType.PLAYER_DEATH:
            self.handle_player_death(data_packet)
        elif packet_type == PacketType.GAME_STATE_UPDATE:
            self.handle_game_state_update(data_packet)
    
    def handle_player_movement(self, data_packet: bytes):
        _, player_id, x, y, z = struct.unpack('Bifff', data_packet)
        self.player_positions[player_id] = (x, y, z)

    def handle_item_pickup(self, data_packet: bytes):
        _, item_id, player_id = struct.unpack('Bii', data_packet)
        self.item_picked_by[item_id] = player_id

    def handle_player_shot(self, data_packet: bytes):
        _, player_id, weapon_id, target_id, damage = struct.unpack('Biiii', data_packet)
        # Deduct damage from the targeted player
        self.player_health[target_id] -= damage

    def handle_player_death(self, data_packet: bytes):
        _, player_id, killer_id, weapon_id = struct.unpack('Biii', data_packet)
        # Reset the player's game state after death
        self.player_health[player_id] = 100  # Reset to default health
        self.player_ammo[player_id] = self.default_ammo_count()

    def default_ammo_count(self):
        return {
            "gauntlet": 0,           # Melee weapon, so no ammo
            "machine_gun": 50,
            "shotgun": 0,
            "grenade_launcher": 0,
            "rocket_launcher": 0,
            "lightning_gun": 0,
            "railgun": 0,
            "plasma_gun": 0,
            "bfg": 0
        }

    def handle_game_state_update(self, data_packet: bytes):
        _, player_id, health, machine_gun_ammo, shotgun_ammo, grenade_ammo, rocket_ammo, lightning_ammo, railgun_ammo, plasma_ammo, bfg_ammo = struct.unpack('Biiiiiiiiiii', data_packet)
        self.player_health[player_id] = health
        self.player_ammo[player_id] = {
            "machine_gun": machine_gun_ammo,
            "shotgun": shotgun_ammo,
            "grenade_launcher": grenade_ammo,
            "rocket_launcher": rocket_ammo,
            "lightning_gun": lightning_ammo,
            "railgun": railgun_ammo,
            "plasma_gun": plasma_ammo,
            "bfg": bfg_ammo
        }

    def get_player_position(self, player_id):
        return self.player_positions.get(player_id)

    def get_item_location(self, item_id):
        return self.item_locations.get(item_id)
