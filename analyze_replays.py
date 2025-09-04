import argparse
import os
import glob
import json
from QuakeLiveInterface.replay import ReplayAnalyzer

def analyze_replays(demo_dir):
    """
    Parses all demo files in a directory and prints a summary.
    """
    if not os.path.isdir(demo_dir):
        print(f"Error: Directory not found at '{demo_dir}'")
        return

    # Assuming demos are in a subdirectory of the server's root,
    # where the ql_agent_plugin is running. The plugin should handle the full path.
    # The demo files have extensions like .dm_91
    demo_files = glob.glob(os.path.join(demo_dir, '*.dm_*'))

    if not demo_files:
        print(f"No demo files found in '{demo_dir}'")
        return

    analyzer = ReplayAnalyzer()
    print(f"Found {len(demo_files)} demo files to analyze.")

    for demo_path in demo_files:
        print(f"\n--- Analyzing {os.path.basename(demo_path)} ---")
        parsed_data = analyzer.parse_demo(demo_path)

        if parsed_data:
            print("Successfully parsed demo.")
            # Print some basic info from the demo
            # The structure of the parsed data depends on UberDemoTools.
            # We'll print a few common fields if they exist.
            if 'players' in parsed_data:
                print(f"  Players: {len(parsed_data['players'])}")
            if 'scores' in parsed_data:
                print(f"  Final Score: {parsed_data['scores']}")

            # For more detail, you could dump the whole JSON
            # print(json.dumps(parsed_data, indent=2))
        else:
            print("Failed to parse demo.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Analyze Quake Live demo files.")
    parser.add_argument('demo_dir', type=str, help="The directory containing the demo files.")
    args = parser.parse_args()

    analyze_replays(args.demo_dir)
