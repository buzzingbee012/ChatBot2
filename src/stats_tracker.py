import json
import os
from datetime import datetime
from pathlib import Path

class StatsTracker:
    def __init__(self, stats_file="stats.json"):
        self.stats_file = stats_file
        self.stats = self._load_stats()
    
    def _load_stats(self):
        """Load statistics from JSON file."""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                
                # Migrate legacy integer format to new dict format
                migrated = {}
                for date, value in data.items():
                    if isinstance(value, int):
                        # Old format: just interaction count
                        migrated[date] = {"interactions": value, "tokens": 0, "errors": []}
                    else:
                        # New format: already a dict
                        migrated[date] = value
                        # Ensure all fields exist
                        if "tokens" not in migrated[date]:
                            migrated[date]["tokens"] = 0
                        if "errors" not in migrated[date]:
                            migrated[date]["errors"] = []
                
                return migrated
            except Exception as e:
                print(f"Error loading stats: {e}")
                return {}
        return {}
    
    def _save_stats(self):
        """Save statistics to JSON file."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"Error saving stats: {e}")
    
    def increment_today(self, tokens=0, error=None):
        """Increment today's interaction count and add tokens if provided."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats:
            self.stats[today] = {"interactions": 0, "tokens": 0, "errors": []}
        
        self.stats[today]["interactions"] = self.stats[today].get("interactions", 0) + 1
        if tokens > 0:
            self.stats[today]["tokens"] = self.stats[today].get("tokens", 0) + tokens
        if error:
            if "errors" not in self.stats[today]:
                self.stats[today]["errors"] = []
            self.stats[today]["errors"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": error
            })
        
        self._save_stats()
    
    def get_stats(self):
        """Return all statistics sorted by date."""
        return dict(sorted(self.stats.items(), reverse=True))
    
    def get_total(self):
        """Return total interactions across all days."""
        total = 0
        for day_stats in self.stats.values():
            if isinstance(day_stats, dict):
                total += day_stats.get("interactions", 0)
            else:
                # Legacy format support
                total += day_stats
        return total
    
    def get_total_tokens(self):
        """Return total tokens used across all days."""
        total = 0
        for day_stats in self.stats.values():
            if isinstance(day_stats, dict):
                total += day_stats.get("tokens", 0)
        return total
