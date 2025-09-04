import logging
import numpy as np

logger = logging.getLogger(__name__)

# Estimated coordinates for key locations on the "Campgrounds" map (q3dm6)
CAMPGROUNDS_STRATEGIC_POINTS = [
    {'name': 'Rocket Launcher', 'pos': np.array([0, 0, 100])},
    {'name': 'Railgun', 'pos': np.array([1500, 1500, 200])},
    {'name': 'Lightning Gun', 'pos': np.array([-1000, 1000, 0])},
    {'name': 'Mega Health', 'pos': np.array([500, -1000, 50])},
    {'name': 'Red Armor', 'pos': np.array([-1500, -1500, 150])}
]


class RewardSystem:
    """
    Calculates rewards based on changes in the game state.
    """
    def __init__(self, reward_weights=None, strategic_points=None):
        if reward_weights is None:
            self.reward_weights = {
                'item_control': 0.4,
                'damage_and_kills': 0.35,
                'map_control': 0.25,
                'health_penalty': -0.1 # This is a penalty, so it's negative
            }
        else:
            self.reward_weights = reward_weights

        self.strategic_points = strategic_points if strategic_points is not None else CAMPGROUNDS_STRATEGIC_POINTS
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
        """Reward for being close to a strategic point."""
        if not self.strategic_points:
            return 0

        agent_pos_dict = current_state.get_agent().position
        agent_pos = np.array([agent_pos_dict['x'], agent_pos_dict['y'], agent_pos_dict['z']])

        min_dist = float('inf')
        for point in self.strategic_points:
            dist = np.linalg.norm(agent_pos - point['pos'])
            if dist < min_dist:
                min_dist = dist

        # Reward for being closer to the nearest strategic point.
        # The smaller the distance, the higher the reward.
        # We add 1 to avoid division by zero and scale it.
        return 1000 / (min_dist + 1)

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
