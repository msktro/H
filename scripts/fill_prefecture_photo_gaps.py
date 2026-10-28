import json, re, time
from html import unescape
from pathlib import Path
from urllib.parse import quote
import requests

root=Path(__file__).resolve().parents[1]
out=root/'static'/'prefecture_photos'
manifest_path=out/'manifest.json'
rows={r['code']:r for r in json.loads(manifest_path.read_text(encoding='utf-8'))}
# Exact Commons files selected after checking that each depicts the named prefecture.
files={
 '05':('秋田県','Kakunodate.jpg','角館・武家屋敷'),
 '08':('茨城県','Baby blue-eyes,Nemophila,Hitachinaka-city,Japan.jpg','国営ひたち海浜公園のネモフィラ'),
 '23':('愛知県','Nagoya Castle.jpg','名古屋城'),
 '26':('京都府','Kyoto Fushimi Inari Shrine.jpg','伏見稲荷大社'),
 '29':('奈良県','Nara, Tōdai-ji temple, 東大寺, Buddha.jpg','東大寺'),
 '35':('山口県','Motonosumi Shrine.jpg','元乃隅神社'),
 '46':('鹿児島県','Sakurajima Island.jpg','桜島'),
}
def plain(x): return re.sub(r'\s+',' ',re.sub(r'<[^>]*>',' ',unescape(x or ''))).strip()
s=requests.Session(); headers={'User-Agent':'TabideaGraduationDemo/1.0 (student project; photo attribution: see manifest)'}
for code,(pref,title,place) in files.items():
 params={'action':'query','titles':'File:'+title,'prop':'imageinfo','iiprop':'url|mime|extmetadata','iiurlwidth':960,'format':'json'}
 data=s.get('https://commons.wikimedia.org/w/api.php',params=params,headers=headers,timeout=45).json()
 page=next(iter(data['query']['pages'].values())); info=(page.get('imageinfo') or [{}])[0]; meta=info.get('extmetadata',{})
 if not info.get('mime','').startswith('image/'): raise RuntimeError(f'{pref} is not an image: {info.get("mime")}')
 license=plain(meta.get('LicenseShortName',{}).get('value'))
 if not license: raise RuntimeError(f'No clear license for {title}')
 url=info.get('thumburl') or info.get('url')
 resp=None
 for attempt in range(5):
  resp=s.get(url,headers=headers,timeout=(15,90))
  if resp.status_code==429:
   time.sleep(min(60,int(resp.headers.get('Retry-After','15')))); continue
  resp.raise_for_status(); break
 if not resp or not resp.headers.get('content-type','').startswith('image/'): raise RuntimeError(f'Image download failed: {title}')
 filename=f'JP-{code}.jpg'; (out/filename).write_bytes(resp.content)
 rows[code]={'code':code,'prefecture':pref,'file':filename,'place':place,'author':plain(meta.get('Artist',{}).get('value'))[:180], 'license':license,'license_url':plain(meta.get('LicenseUrl',{}).get('value')),'source_title':page.get('title','').removeprefix('File:'),'source_url':'https://commons.wikimedia.org/wiki/'+quote(page.get('title','').replace(' ','_'),safe=':'),'image_url':url,'query':'curated Commons file'}
 print(f'OK {code} {pref}: {title} ({license})',flush=True)
manifest_path.write_text(json.dumps([rows[k] for k in sorted(rows)],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
