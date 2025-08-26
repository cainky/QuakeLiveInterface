import subprocess
import json
import logging
import os

logger = logging.getLogger(__name__)

class ReplayAnalyzer:
    """
    A class to handle parsing and analyzing Quake Live demos using UberDemoTools.
    """
    def __init__(self, udt_executable_path='udt_json'):
        """
        Initializes the ReplayAnalyzer.
        Args:
            udt_executable_path: The path to the udt_json executable.
                                 It's assumed to be in the system's PATH by default.
        """
        self.udt_executable_path = udt_executable_path

    def parse_demo(self, demo_filepath):
        """
        Parses a demo file using UberDemoTools and returns the data as a Python object.
        Args:
            demo_filepath: The path to the .dm_73, .dm_90 or .dm_91 demo file.
        Returns:
            A dictionary containing the parsed demo data, or None on failure.
        """
        if not os.path.exists(demo_filepath):
            logger.error(f"Demo file not found: {demo_filepath}")
            return None

        output_json_path = demo_filepath + '.json'
        command = [self.udt_executable_path, '-j', demo_filepath]

        try:
            logger.info(f"Running UberDemoTools: {' '.join(command)}")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.debug(f"UberDemoTools stdout: {result.stdout}")
            logger.debug(f"UberDemoTools stderr: {result.stderr}")

            if os.path.exists(output_json_path):
                with open(output_json_path, 'r') as f:
                    data = json.load(f)
                os.remove(output_json_path) # Clean up the JSON file
                return data
            else:
                logger.error(f"UberDemoTools did not create the expected JSON file: {output_json_path}")
                return None

        except FileNotFoundError:
            logger.error(f"UberDemoTools executable not found at '{self.udt_executable_path}'. "
                         f"Please ensure it's installed and in your system's PATH.")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"UberDemoTools failed with exit code {e.returncode}:")
            logger.error(f"  Stdout: {e.stdout}")
            logger.error(f"  Stderr: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {output_json_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while parsing the demo: {e}")
            return None
