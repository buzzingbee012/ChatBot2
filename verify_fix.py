
import unittest
from unittest.mock import MagicMock
import sys
import os

# Adjust path to import src
sys.path.append(os.getcwd())

from src.stats_tracker import StatsTracker
from src.firebase_handler import FirebaseHandler

class TestStatsMerge(unittest.TestCase):
    def setUp(self):
        # Mock Config Loading
        self.original_load = StatsTracker._load_stats
        self.original_save = StatsTracker._save_stats
        
        # Prevent actual file I/O
        StatsTracker._load_stats = MagicMock(return_value={})
        StatsTracker._save_stats = MagicMock()
        
    def tearDown(self):
        StatsTracker._load_stats = self.original_load
        StatsTracker._save_stats = self.original_save

    def test_merge_remote_greater(self):
        """Test if local stats update when remote is ahead."""
        # 1. Setup Mock Firebase Handler
        mock_fb = MagicMock(spec=FirebaseHandler)
        mock_fb.enabled = True
        mock_fb.get_stats.return_value = {
            "2023-10-27": {"interactions": 10, "tokens": 100, "errors": []}
        }
        
        # 2. Init Tracker (Mocking config/init flow slightly manually)
        tracker = StatsTracker()
        tracker.firebase_handler = mock_fb
        
        # 3. Simulate correct init sequence call
        tracker._merge_stats(mock_fb.get_stats())
        
        # Verify
        self.assertEqual(tracker.stats["2023-10-27"]["interactions"], 10)
        print("SUCCESS: Remote stats merged (Remote > Local)")

    def test_merge_local_greater(self):
        """Test if local stays ahead if it has more data."""
        # Local has 15, Remote has 10 (e.g. valid offline work)
        StatsTracker._load_stats = MagicMock(return_value={
            "2023-10-27": {"interactions": 15, "tokens": 150, "errors": []}
        })
        
        mock_fb = MagicMock(spec=FirebaseHandler)
        mock_fb.enabled = True
        mock_fb.get_stats.return_value = {
            "2023-10-27": {"interactions": 10, "tokens": 100, "errors": []}
        }
        
        tracker = StatsTracker()
        tracker.firebase_handler = mock_fb
        # Force the local stats to be what we mocked (since __init__ calls load_stats)
        tracker.stats = StatsTracker._load_stats()
        
        tracker._merge_stats(mock_fb.get_stats())
        
        self.assertEqual(tracker.stats["2023-10-27"]["interactions"], 15)
        print("SUCCESS: Local stats preserved (Local > Remote)")

    def test_merge_new_local_data(self):
        """Test merging when local has a new day not in remote."""
        StatsTracker._load_stats = MagicMock(return_value={
            "2023-10-28": {"interactions": 5, "tokens": 50, "errors": []}
        })
        
        mock_fb = MagicMock(spec=FirebaseHandler)
        mock_fb.enabled = True
        mock_fb.get_stats.return_value = {
            "2023-10-27": {"interactions": 10, "tokens": 100, "errors": []}
        }
        
        tracker = StatsTracker()
        tracker.firebase_handler = mock_fb
        tracker.stats = StatsTracker._load_stats()
        
        tracker._merge_stats(mock_fb.get_stats())
        
        self.assertEqual(tracker.stats["2023-10-28"]["interactions"], 5)
        self.assertEqual(tracker.stats["2023-10-27"]["interactions"], 10)
        print("SUCCESS: New local day preserved alongside old remote day")

if __name__ == '__main__':
    unittest.main()
