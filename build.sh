#!/usr/bin/env bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers and dependencies
playwright install chromium
playwright install-deps
