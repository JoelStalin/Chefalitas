# -*- coding: utf-8 -*-
"""
Entry point: run the agent (standalone or as Windows service).
"""
import os
import sys

# Run from agent_src/local_printer_agent so imports work
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from config_loader import load_config
from agent_service import run_server

if __name__ == "__main__":
    run_server()
