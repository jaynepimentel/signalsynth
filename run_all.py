# run_all.py — End-to-end SignalSynth runner

import os
import subprocess
import time
import platform

def run_scraper():
    print("\n🛰️  STEP 1: Scraping new posts...")
    result = subprocess.run(["python", "scrapers/scrape_signalsynth.py"], shell=True)
    if result.returncode != 0:
        print("❌ Scraping failed.")
        return False
    print("✅ Scraping completed.")
    return True

def run_enrichment():
    print("\n🤖 STEP 2: Running AI enrichment...")
    result = subprocess.run(["python", "precompute_insights.py"], shell=True)
    if result.returncode != 0:
        print("❌ Precompute enrichment failed.")
        return False
    print("✅ Insights enriched.")
    return True

def launch_streamlit():
    print("\n🌐 STEP 3: Launching SignalSynth Streamlit app...")
    if platform.system() == "Windows":
        os.system("start streamlit run app.py")
    elif platform.system() == "Darwin":
        os.system("open -a Terminal.app 'streamlit run app.py'")
    else:
        subprocess.run(["streamlit", "run", "app.py"])

def run_all():
    print("\n🚀 Starting full SignalSynth pipeline...")
    time.sleep(1)

    if not run_scraper():
        return

    if not run_enrichment():
        return

    launch_streamlit()

if __name__ == "__main__":
    run_all()
