
import argparse, subprocess, sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent

def run(script,*args):subprocess.run([sys.executable,str(ROOT/script),*args],cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['snapshot','live'],default='live');a=p.parse_args()
    run('scripts/01_permits.py','--source',a.mode)
    run('scripts/02_roadways.py','--mode',a.mode)
    run('scripts/03_export.py','--mode',a.mode)
    if a.mode=='snapshot':
        old=pd.read_csv(ROOT/'data/processed/reference_2026_utility_permits_enriched.csv')
        new=pd.read_csv(ROOT/'data/processed/snapshot/2026_utility_permits_enriched.csv')
        pd.testing.assert_frame_equal(old,new,check_dtype=False,check_exact=False,rtol=0,atol=1e-8)
        print('REFERENCE REPRODUCTION: EXACT VALUE MATCH across all rows and columns.')
        run('scripts/04_quality.py','--mode',a.mode)
    else:
        print('LIVE MODE: Current API results may differ from the October 14, 2026 snapshot.')
        run('scripts/04_quality.py','--mode',a.mode)

if __name__=='__main__': main()
