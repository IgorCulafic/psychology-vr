"""Create a local diagnostics ZIP; does not start models or upload anything."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'services'))
from diagnostics_export import create_bundle

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=7)
    args = parser.parse_args()
    path, summary = create_bundle(ROOT, args.days)
    print('Diagnostics saved to: ' + str(path))
    print('Resource samples: ' + str(summary['resource_samples']))
    if not summary['resource_samples']:
        print('No resource samples yet. Start the updated game/services, test, then export again.')
    print('Conversation text and audio are excluded. Send this ZIP back for review.')
