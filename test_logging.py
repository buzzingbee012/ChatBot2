import logging
import sys
import os

# Append src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.utils import Logger

def test_logs():
    print("--- Starting Logging Test ---")
    logger = Logger(name="TestBot")
    
    print("Testing INFO log...")
    logger.info("This is an INFO message.")
    
    print("Testing WARNING log...")
    logger.warning("This is a WARNING message.")
    
    print("Testing ERROR log...")
    logger.error("This is an ERROR message.")
    
    print("Testing DEBUG log (should be silent in console)...")
    logger.debug("This is a DEBUG message.")
    
    print("--- Logging Test Finished ---")
    print("Check if logs appeared above between 'Starting' and 'Finished'.")
    print("Also check conversation_logs.txt")

if __name__ == "__main__":
    test_logs()
