import logging
import numpy as np
import copy

logger = logging.getLogger(__name__)

# High-value item classnames that define strategic interest points
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
    Combat-focused reward system for Quake Live duel.

    Design principles:
    1. Frags are the PRIMARY objective (large sparse reward)
    2. Damage is the path to frags (medium dense reward)
    3. Engagement incentive prevents hide-and-seek
    4. Map/item control is secondary (small shaping reward)
    """
    def __init__(self, reward_weights=None, high_value_items=None):
        # Combat-focused weights
        self.frag_reward = 500          # BIG reward for kills - this is the goal
        self.death_penalty = -300       # Significant penalty for dying
        self.damage_dealt_scale = 2.0   # Per point of damage dealt
        self.damage_taken_scale = -0.5  # Per point of damage taken (smaller than dealt)

        # Engagement shaping (prevents wandering)
        self.engagement_scale = 0.01    # Small reward for closing distance
        self.max_engagement_reward = 0.2  # Cap per step (lowered to avoid "distance farming")

        # Item/map control (secondary objectives)
        self.item_pickup_scale = 0.1    # Reduced from before
        self.map_control_scale = 0.001  # Very small per-step positioning reward

        self.high_value_items = high_value_items if high_value_items is not None else HIGH_VALUE_ITEMS
        self.previous_state = None
        self.prev_opponent_dist = None

    def calculate_reward(self, current_state, action):
        """
        Calculates the total reward for the current step.

        Reward breakdown (rough per-episode estimates):
        - Frag: +500 (sparse, but should be biggest component when it happens)
        - Death: -300 (sparse)
        - Damage dealt: ~2 * damage (e.g., 128 damage = +256)
        - Damage taken: ~-0.5 * damage (e.g., 128 damage = -64)
        - Engagement: ~0-50 per episode (small shaping)
        - Items: ~0-20 per episode (secondary)
        - Map control: ~0-10 per episode (minimal)
        """
        if self.previous_state is None:
            self.previous_state = copy.deepcopy(current_state)
            self._update_opponent_distance(current_state)
            return 0

        total_reward = 0

        # === PRIMARY: Combat rewards ===
        combat_reward = self._calculate_combat_reward(current_state)
        total_reward += combat_reward

        # === SECONDARY: Engagement incentive ===
        engagement_reward = self._calculate_engagement_reward(current_state)
        total_reward += engagement_reward

        # === TERTIARY: Item pickups ===
        item_reward = self._calculate_item_reward(current_state)
        total_reward += item_reward * self.item_pickup_scale

        # === MINIMAL: Map control positioning ===
        map_reward = self._calculate_map_control_reward(current_state)
        total_reward += map_reward * self.map_control_scale

        # Update state for next step
        self.previous_state = copy.deepcopy(current_state)
        self._update_opponent_distance(current_state)

        return total_reward

    def _calculate_combat_reward(self, current_state):
        """
        Primary reward: frags, deaths, and damage.
        This should be the dominant component of the reward signal.
        """
        reward = 0
        prev_agent = self.previous_state.get_agent()
        curr_agent = current_state.get_agent()

        if not prev_agent or not curr_agent:
            return 0

        # === DEATH DETECTION (agent died) ===
        if prev_agent.is_alive and not curr_agent.is_alive:
            reward += self.death_penalty
            logger.info(f"[Reward] DEATH detected! Penalty: {self.death_penalty}")

        # === DAMAGE TAKEN ===
        health_lost = max(0, prev_agent.health - curr_agent.health)
        armor_lost = max(0, prev_agent.armor - curr_agent.armor)
        damage_taken = health_lost + armor_lost
        if damage_taken > 0:
            reward += damage_taken * self.damage_taken_scale

        # === FRAG AND DAMAGE DEALT ===
        prev_opponents = {p.steam_id: p for p in self.previous_state.get_opponents()}
        for opp in current_state.get_opponents():
            if opp.steam_id not in prev_opponents:
                continue
            prev_opp = prev_opponents[opp.steam_id]

            # Damage dealt
            if opp.health < prev_opp.health:
                damage_dealt = prev_opp.health - opp.health
                reward += damage_dealt * self.damage_dealt_scale

            # FRAG (opponent died)
            if prev_opp.is_alive and not opp.is_alive:
                reward += self.frag_reward
                logger.info(f"[Reward] FRAG detected! Reward: {self.frag_reward}")

        return reward

    def _calculate_engagement_reward(self, current_state):
        """
        Small shaping reward for closing distance to opponent.
        Prevents the agent from learning to hide/wander.
        """
        if self.prev_opponent_dist is None:
            return 0

        agent = current_state.get_agent()
        opponents = current_state.get_opponents()

        if not agent or not opponents:
            return 0

        # Get distance to closest opponent
        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])

        min_dist = float('inf')
        for opp in opponents:
            if opp.is_alive:
                opp_pos = np.array([opp.position['x'], opp.position['y'], opp.position['z']])
                dist = np.linalg.norm(agent_pos - opp_pos)
                min_dist = min(min_dist, dist)

        if min_dist == float('inf'):
            return 0

        # Reward for reducing distance (positive when closing in)
        dist_delta = self.prev_opponent_dist - min_dist
        reward = dist_delta * self.engagement_scale

        # Clip to prevent huge rewards from teleports/respawns
        reward = np.clip(reward, -self.max_engagement_reward, self.max_engagement_reward)

        return reward

    def _update_opponent_distance(self, current_state):
        """Track distance to closest opponent for engagement reward."""
        agent = current_state.get_agent()
        opponents = current_state.get_opponents()

        if not agent or not opponents:
            self.prev_opponent_dist = None
            return

        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])

        min_dist = float('inf')
        for opp in opponents:
            if opp.is_alive:
                opp_pos = np.array([opp.position['x'], opp.position['y'], opp.position['z']])
                dist = np.linalg.norm(agent_pos - opp_pos)
                min_dist = min(min_dist, dist)

        self.prev_opponent_dist = min_dist if min_dist != float('inf') else None

    def _calculate_item_reward(self, current_state):
        """Reward for picking up items (reduced importance)."""
        reward = 0
        prev_agent = self.previous_state.get_agent()
        curr_agent = current_state.get_agent()

        if not prev_agent or not curr_agent:
            return 0

        # Health and Armor pickups
        if curr_agent.health > prev_agent.health:
            reward += (curr_agent.health - prev_agent.health)
        if curr_agent.armor > prev_agent.armor:
            reward += (curr_agent.armor - prev_agent.armor)

        # Weapon pickups (smaller bonus)
        prev_weapons = {w.name: w.ammo for w in prev_agent.weapons}
        for w in curr_agent.weapons:
            if w.name not in prev_weapons:
                reward += 20  # New weapon (reduced from 50)

        return reward

    def _calculate_map_control_reward(self, current_state):
        """
        Minimal positioning reward near high-value items.
        Kept very small to not dominate combat rewards.
        """
        items = current_state.get_items()
        agent = current_state.get_agent()

        if not items or not agent:
            return 0

        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])

        total_reward = 0
        for item in items:
            item_name = item.name if hasattr(item, 'name') else item.get('name', '')
            item_value = self.high_value_items.get(item_name, 0)

            if item_value > 0:
                if hasattr(item, 'position'):
                    item_pos_dict = item.position
                else:
                    item_pos_dict = item.get('position', {'x': 0, 'y': 0, 'z': 0})

                item_pos = np.array([item_pos_dict['x'], item_pos_dict['y'], item_pos_dict['z']])
                dist = np.linalg.norm(agent_pos - item_pos)

                # Very small reward, mainly for tiebreaking
                total_reward += (item_value / (dist + 500))

        return total_reward

    def reset(self):
        """Resets the internal state of the reward system."""
        self.previous_state = None
        self.prev_opponent_dist = None
