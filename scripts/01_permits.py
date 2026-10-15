"""
purpose
Extract ArcGIS permit locations and apply transparent, applicant-based filters."""

import argparse
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_APPS/DDOT_TOPS/MapServer/24/query"

WHERE = "((ApplicationDate >= TIMESTAMP '2026-01-01 00:00:00' AND ApplicationDate < TIMESTAMP '2027-01-01 00:00:00') " \
            "OR (IssueDate >= TIMESTAMP '2026-01-01 00:00:00' AND IssueDate < TIMESTAMP '2027-01-01 00:00:00')) " \
            "AND EventTypeDescription IN ('Construction Staging Area','Mobile Crane Work Zone')"

FIELDS = ['OBJECTID','TrackingNumber','PermitNumber','StatusDescription','EventTypeDescription','ApplicationDate','IssueDate',
          'ApplicantCompany','OwnerName','PermitteeName','LocationID','WorkLocationFullAddress','MultiAddresses','Longitude','Latitude',
          'RoadwaySegID','StreetSegID']

UTILITIES = {'DCWATER/CIP':'DC Water','DCWATER/OPS':'DC Water','DCWATER':'DC Water',
             'POTOMAC ELECTRIC POWER COMPANY':'PEPCO','PEPCO':'PEPCO',
             'WASH GAS & LIGHT CO.':'Washington Gas'}

TYPES={'Construction Staging Area','Mobile Crane Work Zone'}

def request(session, args):
    response=session.post(BASE,data={**args,'f':'json'},timeout=90)
    response.raise_for_status(); data=response.json()
    if 'error' in data: raise RuntimeError(data['error'])
    return data

def extract():
    with requests.Session() as session:
        ids=sorted(request(session,{'where':WHERE,'returnIdsOnly':'true'}).get('objectIds') or [])
        rows=[]
        for i in range(0,len(ids),500):
            batch=ids[i:i+500]
            data=request(session,{'objectIds':','.join(map(str,batch)),'outFields':','.join(FIELDS),'returnGeometry':'false'})
            fetched=[item['attributes'] for item in data.get('features',[])]
            if set(x['OBJECTID'] for x in fetched)!=set(batch): raise ValueError('API batch mismatch')
            rows.extend(fetched)
    df=pd.DataFrame(rows)
    if not df['OBJECTID'].is_unique: raise ValueError('Duplicate source IDs')
    # Preserve live ArcGIS millisecond timestamps in the immutable source extract.
    target=ROOT/'data/raw/2026_candidate_permits.csv'; target.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(target,index=False)
    return df

def filter_records(df):
    df=df.copy()
    for c in ['ApplicationDate','IssueDate']:
        values=df[c]
        if pd.api.types.is_numeric_dtype(values):
            times=pd.to_datetime(values,unit='ms',utc=True,errors='coerce')
        else:
            times=pd.to_datetime(values,utc=True,errors='coerce')
        df[c]=times.dt.tz_convert('America/New_York')
    key=df['ApplicantCompany'].fillna('').astype(str).str.strip().str.upper().str.replace(r'\s+',' ',regex=True)
    df['Utility']=key.map(UTILITIES)
    start=pd.Timestamp('2026-01-01',tz='America/New_York'); end=pd.Timestamp('2027-01-01',tz='America/New_York')
    valid=(df['ApplicationDate'].ge(start)&df['ApplicationDate'].lt(end)) | (df['IssueDate'].ge(start)&df['IssueDate'].lt(end))
    df=df.loc[valid & df['EventTypeDescription'].isin(TYPES) & df['Utility'].notna()].copy()
    df=df.drop(columns=['UtilityCandidate','ApplicantCompanyNormalized'],errors='ignore')
    if not df['OBJECTID'].is_unique or df.duplicated(['TrackingNumber','LocationID']).any(): raise ValueError('Invalid location grain')
    if df[['Longitude','Latitude']].isna().any().any(): raise ValueError('Null coordinates')
    return df.sort_values(['TrackingNumber','LocationID'])

def main():
    p=argparse.ArgumentParser(); p.add_argument('--source',choices=['snapshot','live'],default='snapshot');a=p.parse_args()
    df=extract() if a.source=='live' else pd.read_csv(ROOT/'data/raw/2026_candidate_permits.csv')
    filtered=filter_records(df)
    target=ROOT/'data/processed/2026_utility_permits.csv';target.parent.mkdir(parents=True,exist_ok=True)
    filtered.to_csv(target,index=False)
    print('Extract/filter:',len(df),'candidate rows ->',len(filtered),'utility locations; permits:',filtered.TrackingNumber.nunique())

if __name__=='__main__': main()
