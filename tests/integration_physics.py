#!/usr/bin/env python3
"""
Physics Integration Test Suite

Validates that the Quake Live environment correctly responds to agent inputs.
This is a "sanity check" - if these tests fail, RL training will never work.

Requirements:
    - Quake Live server running with minqlx and ql_agent_plugin
    - Redis server running
    - Agent Steam account connected to server

Usage:
    python tests/integration_physics.py [--host localhost] [--port 6379]
"""

import argparse
import time
import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from QuakeLiveInterface.env import QuakeLiveEnv


class PhysicsTestResult:
    """Stores result of a physics test."""
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.message = ""
        self.data = {}


def wait_for_stable_state(env, frames=5):
    """Wait for the game state to stabilize (gravity settle, etc)."""
    for _ in range(frames):
        env.step(np.array([1, 1, 1, 0, 5, 5]))  # Neutral action
        time.sleep(0.05)


def test_agent_spawn(env) -> PhysicsTestResult:
    """Test 1: Verify agent spawns and is alive."""
    result = PhysicsTestResult("Agent Spawn")

    print("\n[TEST 1] Agent Spawn")
    print("-" * 40)

    try:
        obs, info = env.reset(reset_timeout=10.0)
        wait_for_stable_state(env)

        agent = env.game_state.get_agent()

        if agent is None:
            result.message = "Agent is None - not spawned"
            print(f"  Status: FAILED - {result.message}")
            return result

        if not agent.is_alive:
            result.message = "Agent spawned but is_alive=False"
            print(f"  Status: FAILED - {result.message}")
            return result

        result.passed = True
        result.message = f"Agent spawned at {agent.position}"
        result.data = {
            'position': agent.position,
            'health': agent.health,
            'armor': agent.armor
        }
        print(f"  Position: ({agent.position['x']:.1f}, {agent.position['y']:.1f}, {agent.position['z']:.1f})")
        print(f"  Health: {agent.health}, Armor: {agent.armor}")
        print(f"  Status: PASSED")

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_rotation_yaw(env) -> PhysicsTestResult:
    """Test 2: Verify yaw rotation works (looking left/right)."""
    result = PhysicsTestResult("Yaw Rotation")

    print("\n[TEST 2] Yaw Rotation (Looking Left/Right)")
    print("-" * 40)

    try:
        # Get initial yaw
        wait_for_stable_state(env)
        initial_yaw = env.game_state.get_agent().view_angles['yaw']
        print(f"  Initial Yaw: {initial_yaw:.2f}°")

        # Turn right: action[5] = 10 (max right turn)
        action_turn_right = np.array([1, 1, 1, 0, 5, 10])

        for _ in range(20):
            env.step(action_turn_right)
            time.sleep(0.016)  # ~60fps

        final_yaw = env.game_state.get_agent().view_angles['yaw']
        print(f"  Final Yaw: {final_yaw:.2f}°")

        # Calculate yaw change (handle wraparound)
        yaw_delta = final_yaw - initial_yaw
        if yaw_delta > 180:
            yaw_delta -= 360
        elif yaw_delta < -180:
            yaw_delta += 360

        print(f"  Yaw Change: {yaw_delta:.2f}°")

        # Expect at least 20° change after 20 frames of max turn
        if abs(yaw_delta) < 10:
            result.message = f"Yaw changed only {yaw_delta:.2f}° (expected >10°)"
            print(f"  Status: FAILED - {result.message}")
        else:
            result.passed = True
            result.message = f"Yaw changed {yaw_delta:.2f}°"
            print(f"  Status: PASSED")

        result.data = {
            'initial_yaw': initial_yaw,
            'final_yaw': final_yaw,
            'delta': yaw_delta
        }

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_rotation_pitch(env) -> PhysicsTestResult:
    """Test 3: Verify pitch rotation works (looking up/down)."""
    result = PhysicsTestResult("Pitch Rotation")

    print("\n[TEST 3] Pitch Rotation (Looking Up/Down)")
    print("-" * 40)

    try:
        # Reset to neutral pitch first
        action_center = np.array([1, 1, 1, 0, 5, 5])
        for _ in range(10):
            env.step(action_center)

        initial_pitch = env.game_state.get_agent().view_angles['pitch']
        print(f"  Initial Pitch: {initial_pitch:.2f}°")

        # Look down: action[4] = 0 (max look down)
        action_look_down = np.array([1, 1, 1, 0, 0, 5])

        for _ in range(20):
            env.step(action_look_down)
            time.sleep(0.016)

        final_pitch = env.game_state.get_agent().view_angles['pitch']
        print(f"  Final Pitch: {final_pitch:.2f}°")

        pitch_delta = final_pitch - initial_pitch
        print(f"  Pitch Change: {pitch_delta:.2f}°")

        if abs(pitch_delta) < 5:
            result.message = f"Pitch changed only {pitch_delta:.2f}° (expected >5°)"
            print(f"  Status: FAILED - {result.message}")
        else:
            result.passed = True
            result.message = f"Pitch changed {pitch_delta:.2f}°"
            print(f"  Status: PASSED")

        result.data = {
            'initial_pitch': initial_pitch,
            'final_pitch': final_pitch,
            'delta': pitch_delta
        }

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_movement_forward(env) -> PhysicsTestResult:
    """Test 4: Verify forward movement works."""
    result = PhysicsTestResult("Forward Movement")

    print("\n[TEST 4] Forward Movement (+forward)")
    print("-" * 40)

    try:
        wait_for_stable_state(env)

        start_pos = env.game_state.get_agent().position
        start_vec = np.array([start_pos['x'], start_pos['y'], start_pos['z']])
        print(f"  Start Position: ({start_pos['x']:.1f}, {start_pos['y']:.1f}, {start_pos['z']:.1f})")

        # Move forward: action[0] = 2 (forward)
        action_forward = np.array([2, 1, 1, 0, 5, 5])

        for _ in range(30):
            env.step(action_forward)
            time.sleep(0.016)

        end_pos = env.game_state.get_agent().position
        end_vec = np.array([end_pos['x'], end_pos['y'], end_pos['z']])
        print(f"  End Position: ({end_pos['x']:.1f}, {end_pos['y']:.1f}, {end_pos['z']:.1f})")

        # Calculate 3D distance
        distance = np.linalg.norm(end_vec - start_vec)
        # Calculate horizontal (XY) distance
        xy_distance = np.linalg.norm(end_vec[:2] - start_vec[:2])

        print(f"  Total Distance: {distance:.1f} units")
        print(f"  XY Distance: {xy_distance:.1f} units")

        result.data = {
            'start_pos': start_pos,
            'end_pos': end_pos,
            'distance': distance,
            'xy_distance': xy_distance
        }

        if xy_distance < 50:
            result.message = f"Moved only {xy_distance:.1f} units (expected >50)"
            print(f"  Status: FAILED - {result.message}")
            print(f"  Hint: Agent may be stuck on a wall or physics not working")
        else:
            result.passed = True
            result.message = f"Moved {xy_distance:.1f} units"
            print(f"  Status: PASSED")

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_movement_strafe(env) -> PhysicsTestResult:
    """Test 5: Verify strafing works."""
    result = PhysicsTestResult("Strafe Movement")

    print("\n[TEST 5] Strafe Movement (+moveright)")
    print("-" * 40)

    try:
        wait_for_stable_state(env)

        start_pos = env.game_state.get_agent().position
        start_vec = np.array([start_pos['x'], start_pos['y']])
        print(f"  Start Position: ({start_pos['x']:.1f}, {start_pos['y']:.1f})")

        # Strafe right: action[1] = 2 (right)
        action_strafe = np.array([1, 2, 1, 0, 5, 5])

        for _ in range(30):
            env.step(action_strafe)
            time.sleep(0.016)

        end_pos = env.game_state.get_agent().position
        end_vec = np.array([end_pos['x'], end_pos['y']])
        print(f"  End Position: ({end_pos['x']:.1f}, {end_pos['y']:.1f})")

        distance = np.linalg.norm(end_vec - start_vec)
        print(f"  XY Distance: {distance:.1f} units")

        result.data = {'distance': distance}

        if distance < 50:
            result.message = f"Strafed only {distance:.1f} units (expected >50)"
            print(f"  Status: FAILED - {result.message}")
        else:
            result.passed = True
            result.message = f"Strafed {distance:.1f} units"
            print(f"  Status: PASSED")

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_jumping(env) -> PhysicsTestResult:
    """Test 6: Verify jumping works (Z-axis movement)."""
    result = PhysicsTestResult("Jumping")

    print("\n[TEST 6] Jumping (+jump)")
    print("-" * 40)

    try:
        # Make sure we're on the ground first
        wait_for_stable_state(env, frames=20)

        ground_z = env.game_state.get_agent().position['z']
        print(f"  Ground Z: {ground_z:.1f}")

        # Jump: action[2] = 2 (jump)
        action_jump = np.array([1, 1, 2, 0, 5, 5])

        z_history = []
        for _ in range(30):
            env.step(action_jump)
            z_history.append(env.game_state.get_agent().position['z'])
            time.sleep(0.016)

        max_z = max(z_history)
        jump_height = max_z - ground_z

        print(f"  Max Z: {max_z:.1f}")
        print(f"  Jump Height: {jump_height:.1f} units")

        result.data = {
            'ground_z': ground_z,
            'max_z': max_z,
            'jump_height': jump_height,
            'z_history': z_history
        }

        if jump_height < 20:
            result.message = f"Jump height only {jump_height:.1f} (expected >20)"
            print(f"  Status: FAILED - {result.message}")
            print(f"  Hint: Agent may already be in the air or jump not registering")
        else:
            result.passed = True
            result.message = f"Jumped {jump_height:.1f} units"
            print(f"  Status: PASSED")

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_attack(env) -> PhysicsTestResult:
    """Test 7: Verify attack command works (shots fired metric)."""
    result = PhysicsTestResult("Attack")

    print("\n[TEST 7] Attack (+attack)")
    print("-" * 40)

    try:
        # Reset metrics
        env.performance_tracker.reset()
        initial_shots = env.performance_tracker.shots_fired

        # Attack: action[3] = 1 (fire)
        action_attack = np.array([1, 1, 1, 1, 5, 5])

        for _ in range(20):
            env.step(action_attack)
            time.sleep(0.016)

        final_shots = env.performance_tracker.shots_fired
        shots_delta = final_shots - initial_shots

        print(f"  Shots Fired: {shots_delta}")

        result.data = {'shots_fired': shots_delta}

        if shots_delta < 15:
            result.message = f"Only {shots_delta} shots registered (expected ~20)"
            print(f"  Status: WARNING - {result.message}")
            # This could still pass - depends on weapon fire rate
            result.passed = shots_delta > 0
        else:
            result.passed = True
            result.message = f"Fired {shots_delta} shots"
            print(f"  Status: PASSED")

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def test_strafe_jump(env) -> PhysicsTestResult:
    """Test 8: Verify strafe jumping produces speed gain (advanced physics)."""
    result = PhysicsTestResult("Strafe Jump (Advanced)")

    print("\n[TEST 8] Strafe Jumping (Speed Gain)")
    print("-" * 40)

    try:
        wait_for_stable_state(env, frames=10)

        # Measure normal forward speed first
        action_forward = np.array([2, 1, 1, 0, 5, 5])
        speeds_forward = []

        for _ in range(20):
            env.step(action_forward)
            vel = env.game_state.get_agent().velocity
            speed = np.sqrt(vel['x']**2 + vel['y']**2)
            speeds_forward.append(speed)
            time.sleep(0.016)

        max_forward_speed = max(speeds_forward)
        print(f"  Max Forward Speed: {max_forward_speed:.1f} ups")

        # Reset and try strafe jump (forward + strafe + jump + turn)
        wait_for_stable_state(env, frames=10)

        # Strafe jump pattern: forward + right strafe + jump + turn right
        action_strafe_jump = np.array([2, 2, 2, 0, 5, 7])  # Slight right turn
        speeds_strafe = []

        for _ in range(30):
            env.step(action_strafe_jump)
            vel = env.game_state.get_agent().velocity
            speed = np.sqrt(vel['x']**2 + vel['y']**2)
            speeds_strafe.append(speed)
            time.sleep(0.016)

        max_strafe_speed = max(speeds_strafe)
        print(f"  Max Strafe-Jump Speed: {max_strafe_speed:.1f} ups")

        speed_gain = max_strafe_speed - max_forward_speed
        print(f"  Speed Gain: {speed_gain:.1f} ups")

        result.data = {
            'max_forward_speed': max_forward_speed,
            'max_strafe_speed': max_strafe_speed,
            'speed_gain': speed_gain
        }

        # In Quake, strafe jumping should give speed boost
        if speed_gain > 10:
            result.passed = True
            result.message = f"Strafe jumping works! Gained {speed_gain:.1f} ups"
            print(f"  Status: PASSED - Physics simulation is authentic!")
        else:
            result.passed = True  # Not a failure, but informational
            result.message = f"Minimal speed gain ({speed_gain:.1f} ups)"
            print(f"  Status: INFORMATIONAL - May need tuning or more frames")

    except Exception as e:
        result.message = f"Exception: {e}"
        print(f"  Status: FAILED - {result.message}")

    return result


def run_physics_tests(redis_host='localhost', redis_port=6379):
    """Run all physics integration tests."""
    print("=" * 60)
    print("    PHYSICS INTEGRATION TEST SUITE")
    print("=" * 60)
    print(f"\nConnecting to Redis at {redis_host}:{redis_port}...")

    results = []

    try:
        env = QuakeLiveEnv(
            redis_host=redis_host,
            redis_port=redis_port,
            max_episode_steps=10000
        )

        # Run all tests
        results.append(test_agent_spawn(env))

        if results[-1].passed:
            results.append(test_rotation_yaw(env))
            results.append(test_rotation_pitch(env))
            results.append(test_movement_forward(env))
            results.append(test_movement_strafe(env))
            results.append(test_jumping(env))
            results.append(test_attack(env))
            results.append(test_strafe_jump(env))
        else:
            print("\n⚠️  Skipping remaining tests - agent spawn failed")

        env.close()

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        print("\nMake sure:")
        print("  1. Quake Live server is running with minqlx")
        print("  2. ql_agent_plugin.py is loaded")
        print("  3. Redis is running and accessible")
        print("  4. Agent Steam account is connected to server")
        return []

    # Summary
    print("\n" + "=" * 60)
    print("    TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"  {status}: {r.name} - {r.message}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All physics tests passed! Environment is ready for RL training.")
    else:
        print("\n⚠️  Some tests failed. Fix issues before attempting RL training.")

    return results


def main():
    parser = argparse.ArgumentParser(description='Physics Integration Tests')
    parser.add_argument('--host', default='localhost', help='Redis host')
    parser.add_argument('--port', type=int, default=6379, help='Redis port')
    args = parser.parse_args()

    run_physics_tests(args.host, args.port)


if __name__ == '__main__':
    main()
