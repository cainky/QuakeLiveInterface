# QuakeLiveInterface - Quick Start Guide

Get an AI agent running in Quake Live in under 5 minutes.

## Option 1: Docker (Recommended)

The easiest way to run the full stack.

### Prerequisites
- Docker and Docker Compose installed
- A Steam account (for the agent to connect)

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/cainky/QuakeLiveInterface.git
   cd QuakeLiveInterface
   ```

2. **Configure your agent's Steam ID**
   ```bash
   # Create a .env file with your agent's Steam ID
   echo "AGENT_STEAM_ID=76561198012345678" > .env
   ```

   > Get your Steam ID from https://steamid.io/

3. **Start the server stack**
   ```bash
   docker-compose up -d
   ```

   This starts:
   - Quake Live Dedicated Server with minqlx
   - Redis for communication

4. **Install Python dependencies**
   ```bash
   pip install poetry
   poetry install
   ```

5. **Run the visualizer** (in one terminal)
   ```bash
   poetry run python visualizer.py
   ```

6. **Run an agent** (in another terminal)
   ```bash
   # Random agent (baseline)
   poetry run python agents/random_agent.py

   # Or rules-based agent (smarter)
   poetry run python agents/rules_based_agent.py
   ```

7. **Connect your agent's Steam account**

   Launch Quake Live on the agent's Steam account and connect to:
   ```
   localhost:27960
   ```

---

## Option 2: Manual Setup

For advanced users who want full control.

### Prerequisites
- Quake Live Dedicated Server installed
- minqlx installed and configured
- Redis server running
- Python 3.9+

### Steps

1. **Install the Python package**
   ```bash
   git clone https://github.com/cainky/QuakeLiveInterface.git
   cd QuakeLiveInterface
   poetry install
   ```

2. **Copy the minqlx plugin**
   ```bash
   cp minqlx-plugin/ql_agent_plugin.py /path/to/ql/minqlx-plugins/
   ```

3. **Configure your server.cfg**
   ```cfg
   // Add to your server.cfg
   set qlx_plugins "ql_agent_plugin"
   set qlx_redisAddress "localhost"
   set qlx_redisPort "6379"
   set qlx_agentSteamId "YOUR_AGENT_STEAM_ID"
   ```

4. **Start Redis**
   ```bash
   redis-server
   ```

5. **Start the Quake Live server**
   ```bash
   ./run_server_x64_minqlx.sh +exec server.cfg
   ```

6. **Run an agent**
   ```bash
   poetry run python agents/random_agent.py
   ```

---

## Understanding the Action Space

The environment uses a `MultiDiscrete` action space for maximum RL compatibility:

```python
action_space = MultiDiscrete([3, 3, 3, 2, 11, 11])
```

| Index | Action         | Values | Meaning                       |
|-------|----------------|--------|-------------------------------|
| 0     | Forward/Back   | 0,1,2  | 0=back, 1=none, 2=forward     |
| 1     | Left/Right     | 0,1,2  | 0=left, 1=none, 2=right       |
| 2     | Jump/Crouch    | 0,1,2  | 0=crouch, 1=none, 2=jump      |
| 3     | Attack         | 0,1    | 0=no, 1=fire                  |
| 4     | Look Pitch     | 0-10   | Delta: 0=look down, 10=look up|
| 5     | Look Yaw       | 0-10   | Delta: 0=turn left, 10=right  |

**Example: Move forward while strafing right and firing**
```python
action = np.array([2, 2, 1, 1, 5, 5])  # forward, right, no jump, fire, no look change
```

---

## Observation Space

The agent receives a 114-dimensional normalized vector (values in `[-1, 1]`):

| Features        | Dimensions | Description                              |
|-----------------|------------|------------------------------------------|
| Agent           | 11         | pos, vel, pitch, yaw, health, armor, alive |
| Weapons         | 20         | 10 one-hot + 10 ammo levels              |
| Opponents (×3)  | 33         | 11 features × 3 closest opponents        |
| Items (×10)     | 50         | pos, available, spawn_time × 10 items    |

---

## Training with Stable-Baselines3

```python
from stable_baselines3 import PPO
from QuakeLiveInterface.env import QuakeLiveEnv

# Create environment
env = QuakeLiveEnv(
    redis_host='localhost',
    max_episode_steps=1000
)

# Train with PPO
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)

# Save the model
model.save("quake_agent")

# Test the trained agent
obs, info = env.reset()
for _ in range(1000):
    action, _ = model.predict(obs, deterministic=True)
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        obs, info = env.reset()

env.close()
```

---

## Visualizer

Watch your agent in real-time with the 2D map visualizer:

```bash
poetry run python visualizer.py
```

- **Green dot + arrow** = Your agent (arrow shows view direction)
- **Red dots** = Opponents
- **Blue squares** = Weapons
- **Gold squares** = Armor
- **Green squares** = Health
- **Faded items** = Currently respawning

---

## Troubleshooting

### "Connection refused to Redis"
- Ensure Redis is running: `redis-server`
- Check if port 6379 is available

### "Agent not spawning"
- Verify the Steam ID in `qlx_agentSteamId` matches your agent account
- Ensure the agent's Steam account is connected to the server

### "No game state received"
- Check that `ql_agent_plugin.py` is loaded (check server console)
- Verify Redis connection settings match between server and client

### "Agent moves erratically"
- This is expected with random agents!
- Try `rules_based_agent.py` for more sensible behavior

---

## Next Steps

1. **Watch the visualizer** to understand how the bot moves
2. **Modify `rules_based_agent.py`** to experiment with behaviors
3. **Train with RL** using Stable-Baselines3 or RLlib
4. **Record demos** with `demo_dir` parameter for imitation learning

---

## File Structure

```
QuakeLiveInterface/
├── QuakeLiveInterface/      # Main Python package
│   ├── env.py              # Gymnasium environment
│   ├── client.py           # Redis client
│   ├── rewards.py          # Reward calculation
│   └── ...
├── agents/                  # Pre-made agents
│   ├── random_agent.py     # Random baseline
│   └── rules_based_agent.py # Heuristic agent
├── minqlx-plugin/           # Server-side plugin
│   └── ql_agent_plugin.py
├── docker/                  # Docker configuration
├── visualizer.py            # 2D map visualizer
├── docker-compose.yml       # Full stack deployment
└── ARCHITECTURE.md          # Detailed documentation
```
