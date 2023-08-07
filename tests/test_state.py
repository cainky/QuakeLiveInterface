import unittest
from QuakeLiveInterface.state import GameState, PacketType
import struct

class GameStateTest(unittest.TestCase):

    def setUp(self):
        self.game_state = GameState()

    def create_packet(self, packet_type, *args):
        if packet_type == PacketType.PLAYER_MOVEMENT:
            return struct.pack('Bifff', *args)
        elif packet_type == PacketType.ITEM_PICKUP:
            return struct.pack('Biiifff', *args)
        elif packet_type == PacketType.PLAYER_SHOT:
            return struct.pack('Biiii', *args)
        elif packet_type == PacketType.PLAYER_DEATH:
            return struct.pack('Biii', *args)
        elif packet_type == PacketType.GAME_STATE_UPDATE:
            return struct.pack('Biiiiiiiiiii', *args)

    def test_handle_player_movement(self):
        player_id = 1
        position = (10.5, 20.5, 30.5)
        packet = self.create_packet(PacketType.PLAYER_MOVEMENT, packet_type.value, player_id, *position)
        self.game_state.update(packet)
        self.assertEqual(self.game_state.get_player_position(player_id), position)

    def test_handle_item_pickup(self):
        item_id = 2
        player_id = 1
        location = (10.5, 20.5, 30.5)
        packet = self.create_packet(PacketType.ITEM_PICKUP, packet_type.value, item_id, player_id, *location)
        self.game_state.update(packet)
        self.assertEqual(self.game_state.get_item_location(item_id), location)

    def test_handle_player_shot(self):
        target_id = 3
        damage = 50
        packet = self.create_packet(PacketType.PLAYER_SHOT, packet_type.value, 1, 1, target_id, damage)
        self.game_state.player_health[target_id] = 100
        self.game_state.update(packet)
        self.assertEqual(self.game_state.player_health[target_id], 50)

    def test_handle_player_death(self):
        player_id = 1
        killer_id = 2
        packet = self.create_packet(PacketType.PLAYER_DEATH, packet_type.value, player_id, killer_id, 1)
        self.game_state.update(packet)
        self.assertEqual(self.game_state.player_health[player_id], 100)
        self.assertDictEqual(self.game_state.player_ammo[player_id], self.game_state.default_ammo_count())

    def test_handle_game_state_update(self):
        player_id = 1
        health = 50
        ammo_values = [50, 10, 5, 5, 10, 20, 30, 40]
        packet = self.create_packet(PacketType.GAME_STATE_UPDATE, packet_type.value, player_id, health, *ammo_values)
        self.game_state.update(packet)
        self.assertEqual(self.game_state.player_health[player_id], health)
        self.assertDictEqual(self.game_state.player_ammo[player_id], {
            "machine_gun": 50,
            "shotgun": 10,
            "grenade_launcher": 5,
            "rocket_launcher": 5,
            "lightning_gun": 10,
            "railgun": 20,
            "plasma_gun": 30,
            "bfg": 40
        })

    def test_invalid_packet(self):
        with self.assertRaises(RuntimeError):
            self.game_state.update(b"invalid_packet_data")

if __name__ == "__main__":
    unittest.main()
