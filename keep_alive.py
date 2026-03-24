#!/usr/bin/env python3
"""Lightweight keep-alive endpoint for Streamlit free tier"""

import json
import os
from datetime import datetime

def main():
    """Simple health check that returns minimal data to keep app awake"""
    
    # Check if core files exist (no need to load them fully)
    health = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "files": {
            "precomputed_insights.json": os.path.exists("precomputed_insights.json"),
            "precomputed_clusters.json": os.path.exists("precomputed_clusters.json"),
            "_pipeline_meta.json": os.path.exists("_pipeline_meta.json"),
        }
    }
    
    # Return as JSON for easy parsing by uptime services
    print(json.dumps(health, indent=2))

if __name__ == "__main__":
    main()
