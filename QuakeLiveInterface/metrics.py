import logging
import numpy as np
import copy

logger = logging.getLogger(__name__)

class PerformanceTracker:
    """
    A class to track and log performance metrics for the agent.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        """Resets all the metrics for the start of a new episode."""
        self.damage_dealt = 0
        self.damage_taken = 0
        self.kills = 0
        self.deaths = 0
        self.items_collected = {}
        self.shots_fired = 0
        self.successful_hits = 0
        self.start_time = None
        self.end_time = None
        self.previous_state = None
        self.total_distance_traveled = 0
        self.low_hp_steps = 0  # Steps where opponent HP <= finish threshold
        # Finish window tracking (opp_hp<=25 & in_fov & dist<1000)
        self.finish_steps = 0
        self.finish_shots = 0  # Shots fired during finish window
        # Track initial kill/death counters from minqlx (for delta calculation)
        self._initial_kills = None
        self._initial_deaths = None

    def log_step(self, current_state, action):
        """
        Updates the metrics based on the last step.
        This should be called every step of the environment.

        Args:
            current_state: The current GameState
            action: MultiDiscrete action array [fwd/back, left/right, jump/crouch, attack, pitch, yaw]
                   or legacy dict format
        """
        # Shots fired - handle both MultiDiscrete array and legacy dict format
        attack_value = 0
        try:
            if hasattr(action, '__len__') and len(action) >= 4:
                attack_value = action[3]  # MultiDiscrete format
            elif isinstance(action, dict):
                attack_value = action.get('attack', 0)
        except (KeyError, IndexError, TypeError):
            pass

        if attack_value == 1:
            self.shots_fired += 1

        # Initialize or update kill/death baseline from state (cumulative from minqlx)
        current_kills = getattr(current_state, 'agent_kills', 0)
        current_deaths = getattr(current_state, 'agent_deaths', 0)

        if self._initial_kills is None:
            self._initial_kills = current_kills
            self._initial_deaths = current_deaths
        else:
            # Detect match reset: if cumulative counters decreased, update baseline
            if current_kills < self._initial_kills or current_deaths < self._initial_deaths:
                self._initial_kills = current_kills
                self._initial_deaths = current_deaths

        if self.previous_state is None:
            self.previous_state = copy.deepcopy(current_state)
            return

        prev_agent = self.previous_state.get_agent()
        curr_agent = current_state.get_agent()

        # Safety check - need both agents to compare
        if prev_agent is None or curr_agent is None:
            self.previous_state = copy.deepcopy(current_state)
            return

        # Damage taken
        health_diff = prev_agent.health - curr_agent.health
        armor_diff = prev_agent.armor - curr_agent.armor
        if health_diff > 0: self.damage_taken += health_diff
        if armor_diff > 0: self.damage_taken += armor_diff

        # Damage dealt (health + armor, symmetric with damage_taken)
        prev_opponents = {p.steam_id: p for p in self.previous_state.get_opponents()}
        for opp in current_state.get_opponents():
            if opp.steam_id in prev_opponents:
                prev_opp = prev_opponents[opp.steam_id]
                # Count health damage
                if opp.health < prev_opp.health:
                    health_dmg = prev_opp.health - opp.health
                    self.damage_dealt += health_dmg
                    self.successful_hits += 1
                # Count armor damage
                if opp.armor < prev_opp.armor:
                    armor_dmg = prev_opp.armor - opp.armor
                    self.damage_dealt += armor_dmg
            # Track low HP steps (finish-eligible)
            if opp.is_alive and opp.health <= 25:
                self.low_hp_steps += 1

            # Track finish window (opp_hp<=25 & in_fov & dist<1000)
            if opp.is_alive and opp.health <= 25:
                in_fov = getattr(opp, 'in_fov', True)
                if in_fov:
                    opp_pos = np.array([opp.position['x'], opp.position['y'], opp.position['z']])
                    agent_pos = np.array([curr_agent.position['x'], curr_agent.position['y'], curr_agent.position['z']])
                    dist = np.linalg.norm(agent_pos - opp_pos)
                    if dist < 1000:
                        self.finish_steps += 1
                        if attack_value == 1:
                            self.finish_shots += 1

        # Kills and Deaths: use cumulative counters from minqlx (reliable, survives respawn)
        # Note: current_kills and current_deaths were already fetched at the top of this method
        final_kills = getattr(current_state, 'agent_kills', 0)
        final_deaths = getattr(current_state, 'agent_deaths', 0)
        self.kills = max(0, final_kills - self._initial_kills)
        self.deaths = max(0, final_deaths - self._initial_deaths)

        # Item collection
        if curr_agent.health > prev_agent.health:
            # This is a simplification. A better way is to check item pickup events.
            # For now, we'll just count "healing" as item collection.
            item_name = "Health"
            self.items_collected[item_name] = self.items_collected.get(item_name, 0) + 1
        if curr_agent.armor > prev_agent.armor:
            item_name = "Armor"
            self.items_collected[item_name] = self.items_collected.get(item_name, 0) + 1

        # Movement efficiency
        prev_pos = np.array(list(prev_agent.position.values()))
        curr_pos = np.array(list(curr_agent.position.values()))
        self.total_distance_traveled += np.linalg.norm(curr_pos - prev_pos)

        self.previous_state = copy.deepcopy(current_state)

    def log_episode(self, episode_num):
        """Logs the summary of the episode's performance."""
        accuracy = (self.successful_hits / self.shots_fired) * 100 if self.shots_fired > 0 else 0

        logger.info(f"--- Episode {episode_num} Performance ---")
        logger.info(f"  Kills: {self.kills}, Deaths: {self.deaths}")
        logger.info(f"  Damage Dealt: {self.damage_dealt}, Damage Taken: {self.damage_taken}")
        logger.info(f"  Weapon Accuracy: {accuracy:.2f}% ({self.successful_hits}/{self.shots_fired})")
        logger.info(f"  Items Collected: {self.items_collected}")
        logger.info(f"  Distance Traveled: {self.total_distance_traveled:.2f} units")
        logger.info("------------------------------------")
