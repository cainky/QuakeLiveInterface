import struct
from enum import Enum


class PacketType(Enum):
    PLAYER_MOVEMENT = 1
    ITEM_PICKUP = 2
    PLAYER_SHOT = 3
    PLAYER_DEATH = 4
    GAME_STATE_UPDATE = 5


PACKET_FORMATS = {
    PacketType.PLAYER_MOVEMENT: "Bifff",
    PacketType.ITEM_PICKUP: "Biifff",
    PacketType.PLAYER_SHOT: "Biiii",
    PacketType.PLAYER_DEATH: "Biii",
    PacketType.GAME_STATE_UPDATE: "Biiiiiiiiii",
}


class GameState:
    def __init__(self):
        self.player_positions = {}
        self.item_locations = {}
        self.item_picked_by = {}
        self.player_ammo = {}
        self.player_health = {}

    def get_packet_type(self, data_packet: bytes) -> PacketType:
        try:
            header = struct.unpack("B", data_packet[:1])[0]  # Extract the header byte
            return PacketType(header)
        except struct.error as e:
            raise ValueError("Invalid data packet format") from e

    def update(self, data_packet: bytes):
        try:
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
            else:
                raise ValueError("Invalid packet type")
        except Exception as e:
            raise RuntimeError("Error while updating game state") from e

    def handle_player_movement(self, data_packet: bytes):
        try:
            _, player_id, x, y, z = struct.unpack(
                PACKET_FORMATS[PacketType.PLAYER_MOVEMENT], data_packet
            )
            self.player_positions[player_id] = (x, y, z)
        except struct.error as e:
            raise ValueError("Invalid player movement packet format") from e

    def handle_item_pickup(self, data_packet: bytes):
        try:
            _, item_id, player_id, x, y, z = struct.unpack(
                PACKET_FORMATS[PacketType.ITEM_PICKUP], data_packet
            )
            self.item_picked_by[item_id] = player_id
            self.item_locations[item_id] = (x, y, z)
        except struct.error as e:
            raise ValueError("Invalid item pickup packet format") from e

    def handle_player_shot(self, data_packet: bytes):
        try:
            _, player_id, weapon_id, target_id, damage = struct.unpack(
                PACKET_FORMATS[PacketType.PLAYER_SHOT], data_packet
            )
            # Deduct damage from the targeted player
            self.player_health[target_id] = max(
                0, self.player_health.get(target_id, 100) - damage
            )
        except struct.error as e:
            raise ValueError("Invalid player shot packet format") from e

    def handle_player_death(self, data_packet: bytes):
        try:
            _, player_id, killer_id, weapon_id = struct.unpack(
                PACKET_FORMATS[PacketType.PLAYER_DEATH], data_packet
            )
            # Reset the player's game state after death
            self.player_health[player_id] = 100  # Reset to default health
            self.player_ammo[player_id] = self.default_ammo_count()
        except struct.error as e:
            raise ValueError("Invalid player death packet format") from e

    def default_ammo_count(self):
        return {
            "gauntlet": 0,  # Melee weapon, so no ammo
            "machine_gun": 50,
            "shotgun": 0,
            "grenade_launcher": 0,
            "rocket_launcher": 0,
            "lightning_gun": 0,
            "railgun": 0,
            "plasma_gun": 0,
            "bfg": 0,
        }

    def handle_game_state_update(self, data_packet: bytes):
        try:
            (
                _,
                player_id,
                health,
                machine_gun_ammo,
                shotgun_ammo,
                grenade_ammo,
                rocket_ammo,
                lightning_ammo,
                railgun_ammo,
                plasma_ammo,
                bfg_ammo,
            ) = struct.unpack(PACKET_FORMATS[PacketType.GAME_STATE_UPDATE], data_packet)
            self.player_health[player_id] = health
            self.player_ammo[player_id] = {
                "machine_gun": machine_gun_ammo,
                "shotgun": shotgun_ammo,
                "grenade_launcher": grenade_ammo,
                "rocket_launcher": rocket_ammo,
                "lightning_gun": lightning_ammo,
                "railgun": railgun_ammo,
                "plasma_gun": plasma_ammo,
                "bfg": bfg_ammo,
            }
        except struct.error as e:
            raise ValueError("Invalid game state update packet format") from e

    def get_player_position(self, player_id):
        return self.player_positions.get(player_id)

    def get_item_location(self, item_id):
        return self.item_locations.get(item_id)
