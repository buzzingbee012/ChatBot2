#!/usr/bin/env python
"""
Simple script to display daily interaction statistics.
Run with: python view_stats.py
"""
from src.stats_tracker import StatsTracker

def main():
    tracker = StatsTracker()
    stats = tracker.get_stats()
    total = tracker.get_total()
    
    print("\n" + "="*50)
    print("  DAILY INTERACTION STATISTICS")
    print("="*50)
    
    if not stats:
        print("\nNo interactions recorded yet.")
    else:
        print(f"\nTotal Interactions: {total}\n")
        print(f"{'Date':<15} {'Interactions':<15}")
        print("-" * 30)
        for date, count in stats.items():
            print(f"{date:<15} {count:<15}")
    
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
