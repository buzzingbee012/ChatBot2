import json
import os
from datetime import datetime
from pathlib import Path

import yaml
from .supabase_handler import SupabaseHandler

class StatsTracker:
    def __init__(self, stats_file="stats.json"):
        self.stats_file = stats_file
        self.stats = self._load_stats()
        self.supabase_handler = None
        
        try:
            with open("config.yaml", "r") as f:
                config = yaml.safe_load(f)
                self.supabase_handler = SupabaseHandler(config)
                
            # Sync with Supabase on startup
            if self.supabase_handler and self.supabase_handler.enabled:
                remote_stats = self.supabase_handler.get_stats()
                if remote_stats:
                    self._merge_stats(remote_stats)
                    self._save_stats()
                    
        except Exception as e:
            print(f"StatsTracker: Failed to load config/supabase: {e}")
            
    def _merge_stats(self, remote_stats):
        """Merge remote stats into local stats."""
        for date, r_data in remote_stats.items():
            if date not in self.stats:
                self.stats[date] = r_data
            else:
                l_data = self.stats[date]
                # Ensure structure
                if isinstance(l_data, int): # Legacy fix
                    l_data = {"interactions": l_data, "tokens": 0, "errors": []}
                
                if isinstance(r_data, int):
                    r_data = {"interactions": r_data, "tokens": 0, "errors": []}
                    
                # Merge values - take max for counters
                self.stats[date]["interactions"] = max(l_data.get("interactions", 0), r_data.get("interactions", 0))
                self.stats[date]["tokens"] = max(l_data.get("tokens", 0), r_data.get("tokens", 0))
                
                # Merge errors (append unique)
                l_errors = l_data.get("errors", [])
                r_errors = r_data.get("errors", [])
                
                # Simple dedupe by timestamp + message
                existing_sigs = {f"{e.get('time')}-{e.get('message')}" for e in l_errors}
                
                for err in r_errors:
                    sig = f"{err.get('time')}-{err.get('message')}"
                    if sig not in existing_sigs:
                        l_errors.append(err)
                
                self.stats[date]["errors"] = l_errors
    
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
    
    def increment_today(self, tokens=0, error=None, bot_name="Unknown"):
        """Increment today's interaction count and add tokens if provided."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats:
            self.stats[today] = {
                "interactions": 0, 
                "tokens": 0, 
                "errors": [],
                "bots": {}
            }
        
        # Ensure 'bots' dict exists for legacy data
        if "bots" not in self.stats[today]:
            self.stats[today]["bots"] = {}

        # 1. Update Global Totals
        self.stats[today]["interactions"] = self.stats[today].get("interactions", 0) + 1
        if tokens > 0:
            self.stats[today]["tokens"] = self.stats[today].get("tokens", 0) + tokens
            
        if error:
            if "errors" not in self.stats[today]:
                self.stats[today]["errors"] = []
            self.stats[today]["errors"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"[{bot_name}] {error}", # Prefix error
                "bot": bot_name 
            })

        # 2. Update Bot-Specific Stats
        bots_data = self.stats[today]["bots"]
        if bot_name not in bots_data:
            bots_data[bot_name] = {"interactions": 0, "tokens": 0, "errors": []}
            
        bots_data[bot_name]["interactions"] += 1
        if tokens > 0:
            bots_data[bot_name]["tokens"] += tokens
            
        if error:
            bots_data[bot_name]["errors"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": error
            })
        
        self._save_stats()
        
        # Sync to Supabase
        if self.supabase_handler:
            self.supabase_handler.update_stats(self.stats)
    
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
