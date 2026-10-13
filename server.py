"""NFL Matchup Dashboard — standard-library web server, Python 3.10+."""
import csv, io, json, os, time, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent
PORT=int(os.environ.get('PORT','8765'))
SEASON=int(os.environ.get('NFL_SEASON','2026'))
TTL=int(os.environ.get('CACHE_SECONDS','21600'))
STAT_URL=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{SEASON}.csv'
GAMES_URL='https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv'
CACHE=ROOT/'cache'; CACHE.mkdir(exist_ok=True)

def read_csv(source, filename):
    path=CACHE/filename
    stale=not path.exists() or time.time()-path.stat().st_mtime>TTL
    warning=None
    if stale:
        try:
            request=urllib.request.Request(source, headers={'User-Agent':'NFLMatchupDashboard/1.0','Accept':'text/csv'})
            with urllib.request.urlopen(request,timeout=35) as response:
                data=response.read()
            if len(data)<100 or b'<html' in data[:300].lower(): raise ValueError('Unexpected response')
            temp=path.with_suffix('.tmp'); temp.write_bytes(data); temp.replace(path)
        except Exception as e:
            if not path.exists(): raise RuntimeError(f'Could not retrieve {filename}: {e}') from e
            warning=f'{filename}: using cached data because refresh failed ({e})'
    with path.open('r',encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    return rows,warning,datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()

def number(row,key):
    try:return float(row.get(key) or 0)
    except(ValueError,TypeError):return 0.0

def build():
    stats,w1,t1=read_csv(STAT_URL,f'player_{SEASON}.csv')
    games,w2,t2=read_csv(GAMES_URL,'games.csv')
    stats=[r for r in stats if str(r.get('season'))==str(SEASON) and r.get('season_type')=='REG' and r.get('position') in ('QB','RB','WR','TE') and r.get('player_id')]
    byid={}; defensive={}; maxweek=0
    fields=['passing_yards','passing_tds','attempts','completions','passing_interceptions','carries','rushing_yards','rushing_tds','receptions','targets','receiving_yards','receiving_tds']
    for r in stats:
        try:week=int(r['week'])
        except:continue
        maxweek=max(week,maxweek)
        pid=r['player_id']; team=r.get('team',''); opp=r.get('opponent_team','')
        entry=byid.setdefault(pid,{'id':pid,'name':r.get('player_display_name') or r.get('player_name') or pid,'position':r['position'],'team':team,'headshot':r.get('headshot_url',''),'games':[]})
        entry['team']=team
        row={'week':week,'opponent':opp,'team':team}
        row.update({f:number(r,f) for f in fields})
        entry['games'].append(row)
        if opp:
            d=defensive.setdefault(opp,{})
            k=(week,r['position']); totals=d.setdefault(k,{'week':week,'position':r['position'],'yards':0,'tds':0,'receptions':0,'targets':0,'players':0})
            totals['yards']+=number(r,'passing_yards' if r['position']=='QB' else 'rushing_yards' if r['position']=='RB' else 'receiving_yards')
            totals['tds']+=number(r,'passing_tds' if r['position']=='QB' else 'rushing_tds' if r['position']=='RB' else 'receiving_tds')
            totals['receptions']+=number(r,'receptions');totals['targets']+=number(r,'targets');totals['players']+=1
    players=[]
    for p in byid.values():
        p['games'].sort(key=lambda x:x['week'])
        p['games']=list({g['week']:g for g in p['games']}.values())
        p['games'].sort(key=lambda x:x['week'])
        p['season']={k:round(sum(g[k] for g in p['games']),2) for k in fields}
        p['games_played']=len(p['games'])
        players.append(p)
    # Schedule is used only for matchups not finished at load time; ensure proper opponent mapping.
    future=[]
    for g in games:
        if str(g.get('season'))!=str(SEASON) or g.get('game_type')!='REG':continue
        try:week=int(g.get('week') or 0)
        except:continue
        if week<=maxweek:continue
        future.append({'week':week,'away':g.get('away_team',''),'home':g.get('home_team',''),'date':g.get('gameday',''),'time':g.get('gametime','')})
    nextweek=min((g['week'] for g in future),default=maxweek+1)
    nextgames=[g for g in future if g['week']==nextweek]
    opponent={}
    for g in nextgames:
        opponent[g['home']]=g['away'];opponent[g['away']]=g['home']
    for p in players:p['next_opponent']=opponent.get(p['team'],'BYE / TBD')
    defense=[]
    for team, entries in defensive.items():
        for position in ('QB','RB','WR','TE'):
            samples=sorted((v for (wk,pos),v in entries.items() if pos==position),key=lambda x:x['week'])[-5:]
            if samples:
                defense.append({'team':team,'position':position,'weeks':len(samples),'yards_pg':round(sum(x['yards'] for x in samples)/len(samples),1),'td_pg':round(sum(x['tds'] for x in samples)/len(samples),2),'receptions_pg':round(sum(x['receptions'] for x in samples)/len(samples),1)})
    return {'season':SEASON,'latest_week':maxweek,'next_week':nextweek,'updated_at':datetime.now(timezone.utc).isoformat(),'source_updated_at':{'players':t1,'schedules':t2},'warnings':[x for x in (w1,w2) if x],'players':players,'defense':defense,'next_games':nextgames,'definitions':{'defense':'Last five completed team games; QB passing yards, RB rushing yards, WR/TE receiving yards allowed to the entire position group. Values for RB/WR/TE are group totals, not individual-player yards.','rank':'Highest season total by selected metric.','games':'Regular season only. Games missed are excluded from player per-game averages.'}}

class Handler(BaseHTTPRequestHandler):
    def respond(self,code,body,content_type):
        data=body if isinstance(body,bytes) else body.encode('utf-8')
        self.send_response(code);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self' https: data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/health':
            self.respond(200,'ok','text/plain; charset=utf-8')
        elif path=='/api/data':
            try:self.respond(200,json.dumps(build()),'application/json; charset=utf-8')
            except Exception as e:self.respond(503,json.dumps({'error':str(e)}),'application/json; charset=utf-8')
        elif path in ('/','/index.html'):
            self.respond(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
        else:self.respond(404,'Not found','text/plain')
if __name__=='__main__':
    print(f'NFL dashboard: http://localhost:{PORT}   |   season {SEASON}')
    ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
