# Visual Confirmation Checklist

Use this checklist to manually verify the environment is working correctly
by observing the visualizer while an agent runs.

## Setup

1. Start the server stack:
   ```bash
   docker-compose up -d
   ```

2. Start the visualizer in one terminal:
   ```bash
   poetry run python visualizer.py
   ```

3. Start an agent in another terminal:
   ```bash
   poetry run python agents/random_agent.py
   ```

---

## Checklist

### 1. Agent Visibility
- [ ] **Green dot appears** - Agent is spawned and visible
- [ ] **Green arrow shows direction** - View angle indicator is working
- [ ] **Position updates smoothly** - No teleporting or stuttering

### 2. Movement Physics
- [ ] **Agent moves when running forward** - Dot travels in arrow direction
- [ ] **Agent can strafe** - Sideways movement works
- [ ] **Agent doesn't clip through walls** - Stays within map bounds
- [ ] **Speed varies** - Movement isn't constant (acceleration/deceleration)

### 3. Collision Detection
- [ ] **Agent stops at walls** - Doesn't pass through obstacles
- [ ] **Agent follows floor** - Z-axis changes on ramps/stairs
- [ ] **Agent can jump** - Z-axis spikes when jumping

### 4. Opponent Visibility
- [ ] **Red dots appear** - Opponent(s) visible on map
- [ ] **Red dots move** - Opponents are active
- [ ] **Red dots disappear on death** - Only alive opponents shown

### 5. Item Visibility
- [ ] **Blue squares** - Weapons visible
- [ ] **Gold squares** - Armor pickups visible
- [ ] **Green squares** - Health pickups visible
- [ ] **Faded items** - Respawning items are dimmed

### 6. Item Interaction
- [ ] **Items fade when picked up** - Agent passes over item, it dims
- [ ] **Items reappear after respawn** - Faded items become solid again

### 7. Frame Rate
- [ ] **Smooth updates** - 30+ FPS feel (no stuttering)
- [ ] **No long freezes** - Max 1-2 frame drops acceptable
- [ ] **Consistent timing** - Updates feel regular

### 8. Status Text
- [ ] **Health updates** - Shows current health value
- [ ] **Armor updates** - Shows current armor value
- [ ] **Position updates** - Coordinates change with movement
- [ ] **Speed shows** - Velocity magnitude displayed
- [ ] **Game status** - Shows "IN PROGRESS" during play

---

## Common Issues

### Agent doesn't move
1. Check that the agent Steam account is connected
2. Verify `qlx_agentSteamId` matches the connected account
3. Check server console for plugin errors

### Visualizer shows nothing
1. Verify Redis is running: `redis-cli ping`
2. Check server is publishing: `redis-cli subscribe ql:game:state`
3. Ensure agent is spawned in game

### Choppy/stuttering updates
1. Check Redis latency: `python tests/benchmark_latency.py`
2. Monitor network (if Redis is remote)
3. Check for Python GC pauses

### Agent clips through walls
1. This indicates physics simulation issue
2. Check `user_cmd` is being applied in plugin
3. May need to adjust movement values (127 too high?)

### Items don't update
1. Verify `minqlx.items()` returns data in server console
2. Check item serialization in plugin
3. May be map-specific issue

---

## Recording Results

| Test | Pass/Fail | Notes |
|------|-----------|-------|
| Agent Visibility | | |
| Movement Physics | | |
| Collision Detection | | |
| Opponent Visibility | | |
| Item Visibility | | |
| Item Interaction | | |
| Frame Rate | | |
| Status Text | | |

**Overall Status:** [ ] PASS / [ ] FAIL

**Tester:** _______________
**Date:** _______________
**Server Version:** _______________
**Notes:**

```
(Additional observations here)
```
