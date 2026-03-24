#!/usr/bin/env python3
"""Health check for Streamlit deployment — tests all critical components"""

import os, sys, json, traceback
from pathlib import Path

def check_file_exists(path):
    """Check if file exists and show size"""
    p = Path(path)
    if p.exists():
        size_mb = p.stat().st_size / 1024 / 1024
        print(f"✅ {path}: {size_mb:.1f} MB")
        return True
    else:
        print(f"❌ {path}: MISSING")
        return False

def check_json_valid(path):
    """Check if JSON is valid"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ {path}: Valid JSON ({len(data)} items)")
        return True
    except Exception as e:
        print(f"❌ {path}: Invalid JSON - {e}")
        return False

def check_imports():
    """Check critical imports"""
    imports = {
        'streamlit': 'st',
        'openai': 'OpenAI',
        'numpy': 'np',
        'sentence_transformers': 'SentenceTransformer',
        'rank_bm25': 'BM25Okapi',
        'dotenv': 'load_dotenv',
        'fuzzywuzzy': 'fuzz',
        'bs4': 'BeautifulSoup',
    }
    
    print("\n📦 Checking imports:")
    for module, attr in imports.items():
        try:
            if module == 'sentence_transformers':
                # This often fails on Streamlit Cloud
                import sentence_transformers
                print(f"✅ {module}: OK")
            else:
                exec(f"import {module}")
                print(f"✅ {module}: OK")
        except ImportError as e:
            print(f"❌ {module}: MISSING - {e}")

def check_openai_key():
    """Check OpenAI key configuration"""
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.expanduser(os.path.join("~", "signalsynth", ".env")), override=True)
    
    key = os.getenv("OPENAI_API_KEY")
    if key and "YOUR_" not in key.upper():
        print(f"✅ OpenAI key: Configured (sk-{key[:8]}...)")
        return True
    else:
        print(f"❌ OpenAI key: Not configured or placeholder")
        return False

def check_data_integrity():
    """Check core data files"""
    print("\n📁 Checking data files:")
    files = [
        "precomputed_insights.json",
        "precomputed_clusters.json",
        "_pipeline_meta.json",
    ]
    
    all_ok = True
    for f in files:
        if check_file_exists(f):
            if f.endswith('.json'):
                all_ok &= check_json_valid(f)
        else:
            all_ok = False
    
    return all_ok

def check_memory_usage():
    """Estimate memory usage"""
    print("\n💾 Memory usage estimate:")
    
    # Load insights and estimate memory
    try:
        with open("precomputed_insights.json", 'r', encoding='utf-8') as f:
            insights = json.load(f)
        
        # Rough memory calculation
        avg_insight_size = len(str(insights[0])) if insights else 0
        total_mb = len(insights) * avg_insight_size / 1024 / 1024
        
        print(f"📊 Insights: {len(insights)} items ~{total_mb:.1f} MB in memory")
        
        # Check clusters
        with open("precomputed_clusters.json", 'r', encoding='utf-8') as f:
            clusters = json.load(f)
        cluster_mb = len(str(clusters)) / 1024 / 1024
        print(f"📊 Clusters: ~{cluster_mb:.1f} MB in memory")
        
        total_estimated = total_mb + cluster_mb + 100  # +100MB for app overhead
        print(f"📊 Total estimated: ~{total_estimated:.0f} MB")
        
        if total_estimated > 500:
            print("⚠️  WARNING: Memory usage may exceed Streamlit Cloud limits (1GB)")
        elif total_estimated > 300:
            print("⚠️  CAUTION: High memory usage, but should fit in limits")
        else:
            print("✅ Memory usage looks OK")
            
    except Exception as e:
        print(f"❌ Could not estimate memory: {e}")

def main():
    print("🔍 SignalSynth Health Check")
    print("=" * 50)
    
    # Run all checks
    checks_ok = True
    
    checks_ok &= check_data_integrity()
    check_imports()
    checks_ok &= check_openai_key()
    check_memory_usage()
    
    print("\n" + "=" * 50)
    if checks_ok:
        print("✅ All critical checks passed")
        print("\nIf the app is still crashing, check Streamlit Cloud logs for:")
        print("- Runtime errors during page load")
        print("- Memory limit exceeded")
        print("- Request timeout (>60 seconds)")
    else:
        print("❌ Some checks failed - fix these before deploying")
    
    print("\nNext steps:")
    print("1. Fix any failed checks above")
    print("2. Push fixes to GitHub")
    print("3. Check Streamlit Cloud logs at: https://.Streamlit.app/")
    print("4. If still crashing, add debug prints to app.py")

if __name__ == "__main__":
    main()
