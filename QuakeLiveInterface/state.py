import struct

class GameState:
    def __init__(self):
        self.player_positions = {}
        self.item_locations = {}

    def update(self, data_packet):
        # Unpacking player data
        sequence, player_id, x, y, z = struct.unpack('iifff', data_packet[:20])
        self.player_positions[player_id] = (x, y, z)

        # Assuming rest of the packet is all item data
        item_data = data_packet[20:]
        item_count = len(item_data) // 16  # Assuming each item occupies 16 bytes

        for i in range(item_count):
            offset = i * 16
            item_id, x, y, z = struct.unpack('iifff', item_data[offset:offset+16])
            self.item_locations[item_id] = (x, y, z)

    def get_player_position(self, player_id):
        return self.player_positions.get(player_id)

    def get_item_location(self, item_id):
        return self.item_locations.get(item_id)
