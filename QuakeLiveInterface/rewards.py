import logging

logger = logging.getLogger(__name__)

class RewardSystem:
    """
    Calculates rewards based on changes in the game state.
    """
    def __init__(self, reward_weights=None):
        if reward_weights is None:
            self.reward_weights = {
                'item_control': 0.4,
                'damage_and_kills': 0.35,
                'map_control': 0.25,
                'health_penalty': -0.1 # This is a penalty, so it's negative
            }
        else:
            self.reward_weights = reward_weights

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
        """Reward for picking up items."""
        # This is a simplified logic. It rewards based on the change in armor/health
        # which often corresponds to picking up items.
        reward = 0
        prev_agent = self.previous_state.get_agent()
        curr_agent = current_state.get_agent()

        if curr_agent.health > prev_agent.health:
            reward += (curr_agent.health - prev_agent.health)
        if curr_agent.armor > prev_agent.armor:
            reward += (curr_agent.armor - prev_agent.armor)

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
        """Reward for being in a good position."""
        # This is a very simple placeholder. A better implementation would
        # have a list of strategic points on the map.
        # For now, we'll just reward being near the center of the map.
        agent_pos = current_state.get_agent().position
        dist_to_center = (agent_pos['x']**2 + agent_pos['y']**2)**0.5
        return 1 / (1 + dist_to_center / 1000) # Reward for being closer to center

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
