
import os
import json
from datetime import datetime
from src.stats_tracker import StatsTracker

def test_repro():
    stats_file = "repro_stats.json"
    
    # Clean up previous run
    if os.path.exists(stats_file):
        os.remove(stats_file)
        
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Create initial state simulating a run earlier today
    initial_data = {
        today: {
            "interactions": 10,
            "tokens": 500,
            "errors": []
        },
        "2020-01-01": { # Old data to ensure it persists
            "interactions": 5, 
            "tokens": 0, 
            "errors": []
        }
    }
    
    with open(stats_file, 'w') as f:
        json.dump(initial_data, f)
        
    print("Initial stats created.")
    
    # 2. First Run of the Script (Simulated)
    print("--- Simulating Run 1 ---")
    tracker1 = StatsTracker(stats_file=stats_file)
    print(f"Loaded stats: {tracker1.get_stats()}")
    
    # Verify loaded correctly
    if tracker1.stats.get(today, {}).get("interactions") != 10:
        print("FAIL: Did not load initial stats correctly.")
    else:
        print("SUCCESS: Loaded initial stats.")
        
    # Increment
    tracker1.increment_today(tokens=10)
    print(f"Stats after increment: {tracker1.get_stats()}")
    
    # Verify increment
    if tracker1.stats[today]["interactions"] != 11:
         print("FAIL: Did not increment interactions.")
    
    # 3. Second Run of the Script (Simulated) - Initialize NEW tracker
    print("--- Simulating Run 2 ---")
    tracker2 = StatsTracker(stats_file=stats_file)
    print(f"Loaded stats (Run 2): {tracker2.get_stats()}")
    
    if tracker2.stats.get(today, {}).get("interactions") != 11:
        print(f"FAIL: Run 2 loaded {tracker2.stats.get(today, {}).get('interactions')} interactions instead of 11. Data might have been wiped or not saved.")
    else:
        print("SUCCESS: Run 2 loaded correct stats.")

    tracker2.increment_today(tokens=10)
    print(f"Stats after Run 2 increment: {tracker2.get_stats()}")
    
    # Check if 'today' reset to 1
    if tracker2.stats[today]["interactions"] == 1:
        print("CRITICAL FAIL: Stats reset to 1 on second run!")
    elif tracker2.stats[today]["interactions"] == 12:
        print("SUCCESS: Stats accumulated correctly.")
    else:
        print(f"FAIL: Unexpected value: {tracker2.stats[today]['interactions']}")

if __name__ == "__main__":
    test_repro()
