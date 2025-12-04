import logging
import numpy as np

logger = logging.getLogger(__name__)

# High-value item classnames that define strategic interest points
# These are automatically extracted from the game's item list
HIGH_VALUE_ITEMS = {
    'item_health_mega': 100,      # Mega Health - highest priority
    'item_armor_body': 80,        # Red Armor
    'item_armor_combat': 50,      # Yellow Armor
    'weapon_rocketlauncher': 60,  # RL
    'weapon_railgun': 55,         # RG
    'weapon_lightning': 50,       # LG
    'item_quad': 100,             # Quad Damage
    'item_regen': 80,             # Regeneration
    'holdable_medkit': 40,        # Medkit
}


class RewardSystem:
    """
    Calculates rewards based on changes in the game state.

    Uses dynamic item positions from the game state for map control rewards,
    eliminating the need for hardcoded map-specific coordinates.
    """
    def __init__(self, reward_weights=None, high_value_items=None):
        if reward_weights is None:
            self.reward_weights = {
                'item_control': 0.4,
                'damage_and_kills': 0.35,
                'map_control': 0.25,
                'health_penalty': -0.1  # This is a penalty, so it's negative
            }
        else:
            self.reward_weights = reward_weights

        # Item classnames and their strategic value (used for map control reward)
        self.high_value_items = high_value_items if high_value_items is not None else HIGH_VALUE_ITEMS
        self.previous_state = None

    def calculate_reward(self, current_state, action):
        """
        Calculates the total reward for the current step.
        """
        if self.previous_state is None:
            self.previous_state = current_state
            return 0

        total_reward = 0

        # Calculate reward components
        item_reward = self._calculate_item_reward(current_state)
        damage_reward = self._calculate_damage_reward(current_state)
        map_control_reward = self._calculate_map_control_reward(current_state)
        health_penalty = self._calculate_health_penalty(current_state)

        # Apply weights
        total_reward += item_reward * self.reward_weights['item_control']
        total_reward += damage_reward * self.reward_weights['damage_and_kills']
        total_reward += map_control_reward * self.reward_weights['map_control']
        total_reward += health_penalty * self.reward_weights['health_penalty']

        # Update the previous state for the next calculation
        self.previous_state = current_state

        return total_reward

    def _calculate_item_reward(self, current_state):
        """Reward for picking up items, including weapons and ammo."""
        reward = 0
        prev_agent = self.previous_state.get_agent()
        curr_agent = current_state.get_agent()

        # Health and Armor pickups
        if curr_agent.health > prev_agent.health:
            reward += (curr_agent.health - prev_agent.health)
        if curr_agent.armor > prev_agent.armor:
            reward += (curr_agent.armor - prev_agent.armor)

        # Weapon and ammo pickups
        prev_weapons = {w.name: w.ammo for w in prev_agent.weapons}
        for w in curr_agent.weapons:
            if w.name not in prev_weapons:
                reward += 50  # Reward for new weapon
            elif w.ammo > prev_weapons[w.name]:
                reward += (w.ammo - prev_weapons[w.name]) # Reward for ammo pickup

        return reward

    def _calculate_damage_reward(self, current_state):
        """Reward for dealing damage and getting kills."""
        reward = 0
        prev_opponents = {p.steam_id: p for p in self.previous_state.get_opponents()}

        for opp in current_state.get_opponents():
            if opp.steam_id in prev_opponents:
                prev_opp = prev_opponents[opp.steam_id]
                if opp.health < prev_opp.health:
                    reward += (prev_opp.health - opp.health) # Damage dealt
                if not opp.is_alive and prev_opp.is_alive:
                    reward += 100 # Kill bonus
        return reward

    def _calculate_map_control_reward(self, current_state):
        """
        Reward for being close to high-value items.

        Uses dynamic item positions from the game state, weighted by item value.
        This automatically works on any map without hardcoded coordinates.
        """
        items = current_state.get_items()
        if not items:
            return 0

        agent = current_state.get_agent()
        if not agent:
            return 0

        agent_pos_dict = agent.position
        agent_pos = np.array([agent_pos_dict['x'], agent_pos_dict['y'], agent_pos_dict['z']])

        total_reward = 0
        for item in items:
            # Get item name - handle both dict and Item object
            item_name = item.name if hasattr(item, 'name') else item.get('name', '')
            item_value = self.high_value_items.get(item_name, 0)

            if item_value > 0:
                # Get item position
                if hasattr(item, 'position'):
                    item_pos_dict = item.position
                else:
                    item_pos_dict = item.get('position', {'x': 0, 'y': 0, 'z': 0})

                item_pos = np.array([item_pos_dict['x'], item_pos_dict['y'], item_pos_dict['z']])
                dist = np.linalg.norm(agent_pos - item_pos)

                # Reward inversely proportional to distance, scaled by item value
                # Higher value items give more reward for being near them
                total_reward += (item_value / (dist + 100))

        return total_reward

    def _calculate_health_penalty(self, current_state):
        """Penalty for taking damage."""
        penalty = 0
        prev_agent = self.previous_state.get_agent()
        curr_agent = current_state.get_agent()

        if curr_agent.health < prev_agent.health:
            penalty += (prev_agent.health - curr_agent.health)
        if curr_agent.armor < prev_agent.armor:
            penalty += (prev_agent.armor - curr_agent.armor)

        return -penalty # Return as a negative value

    def reset(self):
        """Resets the internal state of the reward system."""
        self.previous_state = None
