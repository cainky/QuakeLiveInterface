import unittest
from QuakeLiveInterface.state import GameState, PacketType, PACKET_FORMATS
import struct


class GameStateTest(unittest.TestCase):
    def setUp(self):
        self.game_state = GameState()

    def create_packet(self, packet_type, *args):
        packet_data = PACKET_FORMATS[packet_type]
        return struct.pack(packet_data, packet_type.value, *args)

    def test_handle_player_movement(self):
        player_id = 1
        position = (10.5, 20.5, 30.5)
        packet = self.create_packet(PacketType.PLAYER_MOVEMENT, player_id, *position)
        self.game_state.update(packet)
        self.assertEqual(self.game_state.get_player_position(player_id), position)

    def test_handle_item_pickup(self):
        item_id = 2
        player_id = 1
        location = (10.5, 20.5, 30.5)
        packet = self.create_packet(
            PacketType.ITEM_PICKUP, item_id, player_id, *location
        )
        self.game_state.update(packet)
        self.assertEqual(self.game_state.get_item_location(item_id), location)

    def test_handle_player_shot(self):
        player_id = 1
        weapon_id = 1
        target_id = 3
        damage = 50
        packet = self.create_packet(
            PacketType.PLAYER_SHOT, player_id, weapon_id, target_id, damage
        )
        self.game_state.player_health[target_id] = 100
        self.game_state.update(packet)
        self.assertEqual(self.game_state.player_health[target_id], 50)

    def test_handle_player_death(self):
        player_id = 1
        killer_id = 2
        weapon_id = 1
        packet = self.create_packet(
            PacketType.PLAYER_DEATH, player_id, killer_id, weapon_id
        )
        self.game_state.update(packet)
        self.assertEqual(self.game_state.player_health[player_id], 100)
        self.assertDictEqual(
            self.game_state.player_ammo[player_id], self.game_state.default_ammo_count()
        )

    def test_handle_game_state_update(self):
        player_id = 1
        health = 50
        ammo_values = [50, 10, 5, 5, 10, 20, 30, 40]
        packet = self.create_packet(
            PacketType.GAME_STATE_UPDATE, player_id, health, *ammo_values
        )
        self.game_state.update(packet)
        self.assertEqual(self.game_state.player_health[player_id], health)
        self.assertDictEqual(
            self.game_state.player_ammo[player_id],
            {
                "machine_gun": 50,
                "shotgun": 10,
                "grenade_launcher": 5,
                "rocket_launcher": 5,
                "lightning_gun": 10,
                "railgun": 20,
                "plasma_gun": 30,
                "bfg": 40,
            },
        )

    def test_invalid_packet(self):
        with self.assertRaises(RuntimeError):
            self.game_state.update(b"invalid_packet_data")


if __name__ == "__main__":
    unittest.main()
