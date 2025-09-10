import json
import numpy as np

def estimate_map_dims_from_replay(replay_file_path):
    """
    Estimates the map dimensions from a UberDemoTools JSON replay file.

    This function analyzes a replay file to find the minimum and maximum
    coordinates reached by players, which can be used to estimate the
    map dimensions.

    Args:
        replay_file_path (str): The path to the JSON replay file.

    Returns:
        tuple: A tuple containing the estimated map dimensions (width, height, depth).
    """
    min_coords = np.array([np.inf, np.inf, np.inf])
    max_coords = np.array([-np.inf, -np.inf, -np.inf])

    with open(replay_file_path, 'r') as f:
        replay_data = json.load(f)

    for frame in replay_data.get('frames', []):
        for player in frame.get('players', []):
            pos = player.get('position')
            if pos:
                coords = np.array([pos['x'], pos['y'], pos['z']])
                min_coords = np.minimum(min_coords, coords)
                max_coords = np.maximum(max_coords, coords)

    if np.inf in min_coords or -np.inf in max_coords:
        return (4000, 4000, 1000) # Return a default if no coordinates were found

    # Add a buffer to the dimensions
    map_dims = (max_coords - min_coords) * 1.1
    return tuple(map_dims.tolist())
