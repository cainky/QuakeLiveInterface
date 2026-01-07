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

        # Pitch penalty (prevents floor-staring)
        self.pitch_free_zone = 45.0     # No penalty within ±45°
        self.pitch_max_penalty = 0.05   # Max penalty per step

        # Fire penalty when opponent not in FOV (softened to not suppress exploration)
        self.fire_no_fov_penalty = -0.005

        # Face opponent reward (teaches "turn toward enemy")
        self.face_opponent_reward = 0.01
        self.face_opponent_yaw_threshold = 15.0  # degrees
        self.face_opponent_pitch_threshold = 30.0  # degrees

        # Finish incentive (teaches "close the kill" when opponent is low)
        self.finish_hp_threshold = 25  # opponent HP threshold
        self.finish_reward = 0.05  # per step while opponent is low

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

        # === SECONDARY: Engagement incentive (only when opponent in FOV) ===
        engagement_reward = self._calculate_engagement_reward(current_state)
        total_reward += engagement_reward

        # === TERTIARY: Item pickups ===
        item_reward = self._calculate_item_reward(current_state)
        total_reward += item_reward * self.item_pickup_scale

        # === MINIMAL: Map control positioning ===
        map_reward = self._calculate_map_control_reward(current_state)
        total_reward += map_reward * self.map_control_scale

        # === FACE OPPONENT REWARD (teaches aiming toward enemy) ===
        face_reward = self._calculate_face_opponent_reward(current_state)
        total_reward += face_reward

        # === PITCH PENALTY (prevents floor-staring) ===
        pitch_penalty = self._calculate_pitch_penalty(current_state)
        total_reward += pitch_penalty

        # === FIRE PENALTY when opponent not in FOV ===
        fire_penalty = self._calculate_fire_penalty(current_state, action)
        total_reward += fire_penalty

        # === FINISH INCENTIVE (close the kill when opponent is low) ===
        finish_reward = self._calculate_finish_reward(current_state)
        total_reward += finish_reward

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

            # Damage dealt (health + armor, symmetric with damage_taken)
            damage_dealt = 0
            if opp.health < prev_opp.health:
                damage_dealt += prev_opp.health - opp.health
            if opp.armor < prev_opp.armor:
                damage_dealt += prev_opp.armor - opp.armor
            if damage_dealt > 0:
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
        ONLY applies when opponent is in FOV (prevents floor-stare farming).
        """
        if self.prev_opponent_dist is None:
            return 0

        agent = current_state.get_agent()
        opponents = current_state.get_opponents()

        if not agent or not opponents:
            return 0

        # Check if any opponent is in FOV - partial reward if not (prevents giving up on chase)
        any_in_fov = any(getattr(opp, 'in_fov', True) for opp in opponents if opp.is_alive)
        fov_multiplier = 1.0 if any_in_fov else 0.3

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

        # Apply FOV multiplier (partial reward when not facing opponent)
        reward *= fov_multiplier

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

    def _calculate_face_opponent_reward(self, current_state):
        """
        Small reward for facing toward the opponent.
        Teaches the bridge: turn camera → shoot better → win trades.
        """
        agent = current_state.get_agent()
        opponents = current_state.get_opponents()

        if not agent or not opponents:
            return 0

        # Get agent view angles
        agent_yaw = agent.view_angles.get('yaw', 0)
        agent_pitch = agent.view_angles.get('pitch', 0)

        # Check if pitch is reasonable (not floor/ceiling staring)
        if abs(agent_pitch) > self.face_opponent_pitch_threshold:
            return 0

        agent_pos = np.array([agent.position['x'], agent.position['y'], agent.position['z']])

        # Find closest living opponent
        closest_opp = None
        min_dist = float('inf')
        for opp in opponents:
            if opp.is_alive:
                opp_pos = np.array([opp.position['x'], opp.position['y'], opp.position['z']])
                dist = np.linalg.norm(agent_pos - opp_pos)
                if dist < min_dist:
                    min_dist = dist
                    closest_opp = opp

        if not closest_opp:
            return 0

        # Calculate angle to opponent
        opp_pos = np.array([closest_opp.position['x'], closest_opp.position['y'], closest_opp.position['z']])
        delta = opp_pos - agent_pos
        angle_to_opp = np.degrees(np.arctan2(delta[1], delta[0]))

        # Calculate yaw error (handle wraparound)
        yaw_error = angle_to_opp - agent_yaw
        while yaw_error > 180:
            yaw_error -= 360
        while yaw_error < -180:
            yaw_error += 360

        # Reward if facing opponent within threshold
        if abs(yaw_error) < self.face_opponent_yaw_threshold:
            return self.face_opponent_reward

        return 0

    def _calculate_pitch_penalty(self, current_state):
        """
        Continuous penalty for pitch drift from horizon.
        Quadratic: ~0 at horizon, -0.02 at ±70° (clamp).
        This kills ceiling/floor attractors without being too harsh near horizon.
        """
        agent = current_state.get_agent()
        if not agent:
            return 0

        pitch_deg = agent.view_angles.get('pitch', 0)
        p = abs(pitch_deg)

        # Quadratic penalty: grows smoothly from horizon
        # At |pitch|=70, penalty = -0.02; at |pitch|=35, penalty = -0.005
        penalty = -0.02 * (p / 70.0) ** 2
        return penalty

    def _calculate_fire_penalty(self, current_state, action):
        """
        Penalty for firing:
        1. Base fire cost (-0.005) for any firing - stops perma-shoot
        2. Extra penalty (-0.005) when not in_fov - stops spray-into-wall
        """
        # Check if firing (action[3] == 1)
        is_firing = action[3] == 1 if len(action) > 3 else False
        if not is_firing:
            return 0

        # Base fire cost: -0.005 per step while firing
        # At 40 Hz = -0.2/sec, enough to discourage perma-shoot
        penalty = -0.005

        opponents = current_state.get_opponents()
        if opponents:
            # Extra penalty when not in_fov
            any_in_fov = any(getattr(opp, 'in_fov', True) for opp in opponents if opp.is_alive)
            if not any_in_fov:
                penalty += self.fire_no_fov_penalty  # -0.005 more

        return penalty

    def _calculate_finish_reward(self, current_state):
        """
        Incentive to close the kill when opponent is low HP.
        Teaches "press when you've won the trade" instead of disengaging.
        """
        opponents = current_state.get_opponents()
        if not opponents:
            return 0

        # Check if any opponent is low HP
        for opp in opponents:
            if opp.is_alive and opp.health <= self.finish_hp_threshold:
                return self.finish_reward

        return 0

    def reset(self):
        """Resets the internal state of the reward system."""
        self.previous_state = None
        self.prev_opponent_dist = None
