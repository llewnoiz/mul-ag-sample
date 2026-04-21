#!/usr/bin/env python3
"""
Test script for the Orchestrator Agent
"""

import sys
import os

# Test basic import
try:
    # Add the current directory to path for imports
    sys.path.insert(0, os.path.dirname(__file__))
    
    # Test importing the config class first
    from orchestrator_agent import OrchestratorConfig
    print("✓ OrchestratorConfig imported successfully")
    
    # Test importing the main class
    from orchestrator_agent import OrchestratorAgent
    print("✓ OrchestratorAgent imported successfully")
    
    # Create a basic config
    config = OrchestratorConfig(
        model="global.anthropic.claude-sonnet-4-20250514-v1:0",
        user="test_user"
    )
    print("✓ OrchestratorConfig created successfully")
    
    print("✓ All basic tests passed!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)