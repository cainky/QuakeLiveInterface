# QuakeLiveInterface
![Quake-Live Logo|%20](https://upload.wikimedia.org/wikipedia/de/3/3b/Quake_Live_Logo.png)

QuakeLiveInterface is a Python library designed to provide a comprehensive, object-oriented interface to a Quake Live game server. It serves as a real-time Python interface for Quake Live, allowing you to extract game state and send commands.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPL3-yellow.svg)](https://www.gnu.org/licenses/gpl-3.0.en.html)

## What's New

This project includes a **custom fork of minqlx** with C-level entity introspection:

- **`get_entity_info(entity_id)`** - Direct access to game entities from Python
- **Reliable item tracking** - Query item spawn states, positions, and respawn timers
- **Docker-based build system** - Compiles minqlx from source with our custom patches

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/cainky/QuakeLiveInterface.git
cd QuakeLiveInterface
poetry install

# 2. Start the server stack
docker-compose up -d

# 3. Connect to localhost:27960 in Quake Live

# 4. Verify game state is streaming
poetry run python tools/test_subscribe.py
```

### Parallel Training (4 servers)

```bash
# Start 4 independent Quake servers for parallel RL training
docker-compose -f docker-compose.multi.yml up -d

# Each server uses a unique env_id for Redis namespacing:
#   Server 0: ql:0:agent:*, port 27960
#   Server 1: ql:1:agent:*, port 27961
#   Server 2: ql:2:agent:*, port 27962
#   Server 3: ql:3:agent:*, port 27963
```

## How It Works

```
┌─────────────────┐     ┌─────────────┐     ┌──────────────────┐
│   Quake Live    │────▶│    Redis    │◀────│   Your Code      │
│     Server      │     │   Pub/Sub   │     │                  │
│                 │◀────│             │────▶│ • RL Agents     │
│  minqlx plugin  │     │   ~60Hz     │     │  • Analytics     │
└─────────────────┘     └─────────────┘     │  • Bots          │
        ▲                                   │  • Visualizers   │
        │              Game Commands        │  • Anything!     │
        └───────────────────────────────────└──────────────────┘
```

A minqlx plugin extracts game state at ~60Hz and publishes to Redis. Subscribe to get real-time data, publish commands to control the game.

## Features

- **Real-time Game State**: Position, velocity, health, armor, weapons at ~60Hz
- **Entity Introspection**: C-level `get_entity_info()` for reliable item/powerup tracking
- **Bidirectional**: Read state AND send movement/attack commands
- **Docker Stack**: One command to run Quake Live server + Redis
- **Gymnasium Compatible**: Optional RL environment wrapper included
- **2D Visualizer**: Real-time map viewer for debugging agents
- **Multiple Game Modes**: FFA, Duel, TDM, CTF

## Game State

Subscribe to `ql:game:state` for real-time JSON:

```json
{
  "agent": {
    "steam_id": 72561195012232678,
    "name": "Snap",
    "health": 100,
    "armor": 50,
    "position": {"x": -328.37, "y": 1615.47, "z": 1276.33},
    "velocity": {"x": -419.45, "y": 65.81, "z": -133.0},
    "view_angles": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0},
    "is_alive": true,
    "team": "free"
  },
  "opponents": [
    {
      "steam_id": 72561195012232678,
      "name": "Anarki",
      "health": 125,
      "armor": 100,
      "position": {"x": 512.0, "y": -128.0, "z": 64.0},
      "velocity": {"x": 0.0, "y": 0.0, "z": 0.0},
      "view_angles": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
      "is_alive": true,
      "in_fov": true,
      "team": "free"
    }
  ],
  "items": [
    {"name": "item_armor_mega", "position": {"x": 0, "y": 0, "z": 0}, "is_available": true, "time_to_spawn_ms": 0},
    {"name": "item_health_mega", "position": {"x": -384, "y": 640, "z": 32}, "is_available": false, "time_to_spawn_ms": 35000}
  ],
  "game_in_progress": true,
  "game_type": "duel",
  "map_name": "toxicity",
  "agent_kills": 2,
  "agent_deaths": 1,
  "server_time_ms": 1704567890123,
  "game_time_ms": 45000
}
```

## Sending Commands

Publish to `ql:agent:command`:

```python
import redis
import json

r = redis.Redis('localhost', 6379)

# Movement input (buttons held each frame)
r.publish('ql:agent:command', json.dumps({
    'command': 'input',
    'forward': 1,      # 0 or 1
    'back': 0,
    'left': 0,
    'right': 1,        # Strafe right
    'jump': 1,         # Jump
    'attack': 1,       # Fire
    'pitch_delta': 0,  # Look up/down
    'yaw_delta': 5     # Turn right
}))
```

## Use Cases

### Reinforcement Learning
```python
from stable_baselines3 import PPO
from QuakeLiveInterface.env import QuakeLiveEnv

env = QuakeLiveEnv(redis_host='localhost')
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)
```

### Real-time Visualizer
```bash
poetry run python visualizer.py
```

### Custom Bot
```python
import redis
import json

r = redis.Redis('localhost', 6379, decode_responses=True)
ps = r.pubsub()
ps.subscribe('ql:game:state')

for msg in ps.listen():
    if msg['type'] == 'message':
        state = json.loads(msg['data'])
        # Your logic here
        if state['agent']['health'] < 50:
            # Run away!
            r.publish('ql:agent:command', json.dumps({
                'command': 'input',
                'forward': 1,
                'yaw_delta': 10
            }))
```

### Analytics / Recording
```python
# Log all game events to a file
with open('game_log.jsonl', 'a') as f:
    for msg in ps.listen():
        if msg['type'] == 'message':
            f.write(msg['data'] + '\n')
```

## Configuration

### Environment Variables (docker-compose.yml)

| Variable | Description |
|----------|-------------|
| `QLX_AGENTSTEAMID` | Steam ID of the controlled account |
| `QLX_REDISADDRESS` | Redis hostname (default: `redis`) |
| `MAP_POOL` | Map and game type (e.g., `toxicity\|duel`) |

## Project Structure

```
QuakeLiveInterface/
├── QuakeLiveInterface/       # Python package
│   ├── env.py               # Gymnasium environment
│   ├── client.py            # Redis client wrapper
│   ├── state.py             # Game state parsing
│   └── rewards.py           # Reward functions for RL
├── minqlx-fork/              # Custom minqlx with get_entity_info()
│   ├── dllmain.c            # Entry point and hooks
│   ├── pyminqlx.c           # Python bindings
│   └── python_embed.c       # Custom C API extensions
├── minqlx-plugin/            # Server-side plugin
│   └── ql_agent_plugin.py   # State extraction & Redis pub/sub
├── agents/                   # Example agents
│   ├── random_agent.py
│   └── rules_based_agent.py
├── tools/
│   ├── test_subscribe.py    # Test Redis connection
│   └── simulator.py         # Offline game state simulator
├── tests/                    # Pytest test suite
├── docker-compose.yml        # Full stack deployment
├── Dockerfile.server         # Multi-stage minqlx build
└── visualizer.py             # 2D map viewer
```

## Redis Channels

| Channel | Direction | Description |
|---------|-----------|-------------|
| `ql:game:state` | Server → Client | Game state at ~60Hz |
| `ql:agent:command` | Client → Server | Movement/action commands |
| `ql:admin:command` | Client → Server | Admin commands (restart, record) |
| `ql:game:events` | Server → Client | Damage, frag, death, pickup events |

### Parallel Environment Namespacing

For parallel training, channels are namespaced with `env_id`:

| Single Env | Parallel Env (id=0) | Parallel Env (id=1) |
|------------|---------------------|---------------------|
| `ql:game:state` | `ql:0:game:state` | `ql:1:game:state` |
| `ql:agent:command` | `ql:0:agent:command` | `ql:1:agent:command` |

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Detailed setup guide
- **[minqlx-fork/README.md](minqlx-fork/README.md)** - Custom minqlx build instructions

## Troubleshooting

**"Connection refused to Redis"**
- Ensure Docker containers are running: `docker ps`
- On Windows, use `127.0.0.1:6379:6379` in docker-compose.yml

**"Agent not detected"**
- Verify `QLX_AGENTSTEAMID` matches your Steam account
- Check: `docker exec ql-redis redis-cli GET ql:agent:debug`

**"No game state"**
- Connect to the server with the correct Steam account first

## Testing

```bash
poetry run pytest
```

## Credits

- **[minqlx](https://github.com/MinoMino/minqlx)** by MinoMino - The original minqlx project this fork is based on
- **[lucadamico/quakelive-server](https://hub.docker.com/r/lucadamico/quakelive-server)** - Docker base image for Quake Live server

## License

GPL v3 License - see [LICENSE](LICENSE) for details.
