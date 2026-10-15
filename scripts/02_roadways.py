"""
purpose
Match permit points to non-alley roadway centerlines, or reuse audited snapshot."""

import argparse
import json
import re
import time
from pathlib import Path
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Point, LineString


ROOT=Path(__file__).resolve().parents[1]
ROAD='https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_WebMercator/MapServer/162/query'
TRANSFORM=Transformer.from_crs('EPSG:4326','EPSG:26985',always_xy=True)

ABBR={'STREET':'ST','ROAD':'RD','AVENUE':'AVE','PLACE':'PL','DRIVE':'DR','BOULEVARD':'BLVD','LANE':'LN','COURT':'CT','TERRACE':'TER','CIRCLE':'CIR','PARKWAY':'PKWY','BRIDGE':'BRG','HIGHWAY':'HWY','EXPRESSWAY':'EXPY'}

def norm(value):
    words=re.sub('[^A-Z0-9 ]',' ',str(value or '').upper()).split()
    return ' '.join(ABBR.get(word,word) for word in words)

def name_match(address,road):
    route=norm(road)
    return bool(route and re.search(r'(?<!\w)'+re.escape(route)+r'(?!\w)',norm(address)))

def api_features(session,row):
    point={'x':float(row.Longitude),'y':float(row.Latitude),'spatialReference':{'wkid':4326}}
    params={'where':"ROADTYPE <> '4' AND FHWAFUNCTIONALCLASS IS NOT NULL",'geometry':json.dumps(point),'geometryType':'esriGeometryPoint','inSR':4326,'spatialRel':'esriSpatialRelIntersects','distance':100,'units':'esriSRUnit_Meter','outSR':26985,'outFields':'OBJECTID,SUBBLOCKKEY,ROUTENAME,ROADTYPE,FHWAFUNCTIONALCLASS','returnGeometry':'true','f':'json'}
    for attempt in range(3):
        try:
            resp=session.get(ROAD,params=params,timeout=75);resp.raise_for_status();obj=resp.json()
            if 'error' in obj or obj.get('exceededTransferLimit'): raise RuntimeError(str(obj.get('error','Truncated candidate results')))
            return obj.get('features',[])
        except (requests.RequestException,ValueError,RuntimeError):
            if attempt==2: raise
            time.sleep(2**attempt)

def match(row, session):
    x,y=TRANSFORM.transform(float(row.Longitude),float(row.Latitude)); point=Point(x,y)
    roads=[]
    for feature in api_features(session,row):
        a=feature['attributes'];paths=(feature.get('geometry') or {}).get('paths') or []
        distance=min((point.distance(LineString(path)) for path in paths if len(path)>1),default=None)

        if distance is None:continue
        try: c=int(a['FHWAFUNCTIONALCLASS'])
        except (TypeError,ValueError): continue
        if c not in range(1,8):continue
        route=a.get('ROUTENAME'); direct=name_match(row.WorkLocationFullAddress,route)
        bn=bool(str(route or '').upper().strip().endswith(' BN') and name_match(row.WorkLocationFullAddress,re.sub(r'\s+BN$','',route,flags=re.I)))
        roads.append({'RoadName':route,'SubBlockKey':a.get('SUBBLOCKKEY'),'ProposedFunctionalClass':c,'DistanceMeters':round(distance,2),'StreetNameMatch':direct,'BNNameMatch':bn})
    if not roads:return {'FunctionalClass':None,'ProposedFunctionalClass':None,'MatchStatus':'UNMATCHED','CandidateCount':0}
    roads.sort(key=lambda c:(not (c['StreetNameMatch'] or c['BNNameMatch']),c['DistanceMeters']))
    best=roads[0]; same=[c for c in roads if c['StreetNameMatch'] or c['BNNameMatch']]
    conflict=any(c['ProposedFunctionalClass']!=best['ProposedFunctionalClass'] and abs(c['DistanceMeters']-best['DistanceMeters'])<=2 and c['StreetNameMatch']==best['StreetNameMatch'] and c['BNNameMatch']==best['BNNameMatch'] for c in roads[1:])
    if conflict:status='REVIEW_AMBIGUOUS'
    elif not (best['StreetNameMatch'] or best['BNNameMatch']):status='REVIEW_STREET_NAME'
    elif best['DistanceMeters']>50:status='REVIEW_DISTANT'
    elif best['DistanceMeters']>30:
        status='MATCHED_EXTENDED_PROVISIONAL' if len({c['ProposedFunctionalClass'] for c in same})==1 else 'REVIEW_AMBIGUOUS'
    elif best['BNNameMatch']:status='MATCHED_NORMALIZED'
    else:status='MATCHED'
    accepted=status.startswith('MATCHED')
    return {**best,'FunctionalClass':best['ProposedFunctionalClass'] if accepted else None,'MatchStatus':status,'ResolutionMethod':status,'CandidateCount':len(roads)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['snapshot','live'],default='snapshot');a=p.parse_args()
    permits=pd.read_csv(ROOT/'data/processed/2026_utility_permits.csv')
    if a.mode=='snapshot':
        matches=pd.read_csv(ROOT/'data/processed/roadway_matches_recovered.csv')
        if set(matches.OBJECTID)!=set(permits.OBJECTID):raise ValueError('Snapshot roadway IDs do not match permit snapshot. Run fresh live enrichment instead.')
        print('Using existing 4,983-row audited roadway snapshot; NO API calls')
    else:
        rows=[]
        with requests.Session() as session:
            for i,row in enumerate(permits.itertuples(index=False),1):
                try: result=match(row,session)
                except Exception as exc: result={'MatchStatus':'API_ERROR','FunctionalClass':None,'ErrorMessage':str(exc)}
                rows.append({'OBJECTID':row.OBJECTID,'TrackingNumber':row.TrackingNumber,'LocationID':row.LocationID,'Utility':row.Utility,'WorkLocationFullAddress':row.WorkLocationFullAddress,**result})
                if i%100==0:print('Roadways:',i,'/',len(permits))
        matches=pd.DataFrame(rows)
    target=ROOT/'data/processed/roadway_matches_current.csv';matches.to_csv(target,index=False)
    print('Roadway statuses:',matches.MatchStatus.value_counts().to_dict())

if __name__=='__main__':main()
