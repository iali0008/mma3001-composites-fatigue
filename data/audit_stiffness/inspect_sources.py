from pathlib import Path
import sys,json,hashlib,collections
sys.path.insert(0,str(Path(__file__).parent/'deps'))
import numpy as np
from scipy.io import whosmat,loadmat
from openpyxl import load_workbook
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'2.+Composites'/'2. Composites'
OUT=Path(__file__).parent
def main():
    files=sorted(p for p in SRC.rglob('*') if p.is_file())
    manifest=[dict(path=str(p.relative_to(SRC)),size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns) for p in files]
    (OUT/'original_manifest.json').write_text(json.dumps(manifest,indent=2))
    inventory=[]
    for layup in sorted(SRC.glob('Layup[123]')):
        for specimen in sorted(layup.glob('L*_F')):
            counts=collections.Counter(str(p.parent.relative_to(specimen)) for p in specimen.rglob('*') if p.is_file() and not p.name.startswith('._'))
            inventory.append(dict(layup=layup.name,specimen=specimen.name,counts=dict(counts)))
    (OUT/'inventory.json').write_text(json.dumps(inventory,indent=2))
    lines=[]
    for p in sorted(SRC.rglob('*.xlsx')):
        if p.name.startswith('._'):continue
        w=load_workbook(p,data_only=True)
        lines.append('\nFILE '+str(p.relative_to(SRC)))
        for s in w:
            lines.append('SHEET '+s.title)
            for row in s:
                cells=['%s=%s'%(c.coordinate,c.value) for c in row if c.value is not None]
                if cells:lines.append(' | '.join(cells))
    (OUT/'logbooks.txt').write_text('\n'.join(lines),encoding='utf-8')
    lines=[]
    for item in inventory:
        sp=SRC/item['layup']/item['specimen']
        for folder in sorted(p for p in sp.iterdir() if p.is_dir() and ('strain' in p.name.lower() or 'pzt' in p.name.lower())):
            fs=sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith('._'))
            lines.append('\nFOLDER '+str(folder.relative_to(SRC))+' FILES '+str(len(fs)))
            for p in fs[:2]:
                lines.append(p.name+' '+str(p.stat().st_size))
                if p.suffix=='.mat':
                    try:
                        lines.append(str(whosmat(p)))
                        d=loadmat(p,simplify_cells=True)
                        for k,v in d.items():
                            if k.startswith('__'):continue
                            if isinstance(v,dict):lines.append(k+' dict '+str({a:str(type(b))+str(getattr(b,'shape','')) for a,b in v.items()}))
                            else:lines.append(k+' '+str(getattr(v,'shape',''))+' '+str(v)[:1200])
                    except Exception as e:lines.append('ERROR '+str(e))
                else:lines.append(repr(p.read_bytes()[:700]))
    (OUT/'schemas.txt').write_text('\n'.join(lines),encoding='utf-8')
    try:
        from pypdf import PdfReader
        for p in sorted(SRC.rglob('*.pdf')):
            if 'Documentation' not in str(p) and p.name!='README.pdf':continue
            if 'Documentation' in str(p) and 'Layup1' not in str(p):continue
            name=p.parent.parent.name+'_'+p.name if p.name!='README.pdf' else p.parent.name+'_README.pdf'
            text='\n\n'.join('PAGE '+str(i+1)+'\n'+(page.extract_text() or '') for i,page in enumerate(PdfReader(p).pages))
            (OUT/(name+'.txt')).write_text(text,encoding='utf-8')
    except ImportError: print('PDF dependency unavailable')
    print(json.dumps(inventory,indent=2))
def audit():
    import csv
    def compact(v):
        if isinstance(v,dict):return {k:compact(a) for k,a in v.items()}
        if isinstance(v,(list,tuple)):return [compact(a) for a in v]
        if isinstance(v,np.ndarray):return v.tolist()
        if isinstance(v,np.generic):return v.item()
        return v
    rows=[]; strain=[]; samples={}
    for lay in sorted(SRC.glob('Layup[123]')):
        for sp in sorted(lay.glob('L*_F')):
            print('Inspecting',sp.name,flush=True)
            for p in sorted(sp.rglob('*.mat')):
                if p.name.startswith('._'):continue
                try:d=loadmat(p,simplify_cells=True)
                except Exception as e:
                    rows.append(dict(specimen=sp.name,file=p.name,error=str(e)));continue
                if 'coupon' in d:
                    c=d['coupon']; sg=c.get('straingage_data',{})
                    paths=c.get('path_data',[])
                    if sp.name not in samples:
                        samples[sp.name]=compact({k:v for k,v in c.items() if k!='path_data'})
                        samples[sp.name]['path_sample']=str(paths[0])[:1600] if len(paths) else ''
                    row=dict(layup=lay.name,specimen=sp.name,file=p.name,cycles=compact(c.get('cycles')),load=compact(c.get('load')),condition=compact(c.get('condition')),comment=compact(c.get('comment')),strain=compact(sg),path_count=len(paths))
                    rows.append(row)
                else:
                    summary={}
                    for k,v in d.items():
                        if k.startswith('__'):continue
                        a=np.asarray(v)
                        summary[k]=dict(shape=list(a.shape),finite=int(np.isfinite(a).sum()),n=int(a.size),min=float(np.nanmin(a)),max=float(np.nanmax(a)),mean=float(np.nanmean(a)),std=float(np.nanstd(a)))
                    strain.append(dict(layup=lay.name,specimen=sp.name,file=p.name,fields=summary))
    (OUT/'pzt_metadata.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (OUT/'strain_profile.json').write_text(json.dumps(strain,indent=2),encoding='utf-8')
    (OUT/'coupon_samples.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')
    for lay in ['Layup1','Layup2','Layup3']:
        for sp in sorted({r['specimen'] for r in rows if r.get('layup')==lay}):
            rs=[r for r in rows if r['specimen']==sp]
            labels=[r for r in rs if np.asarray(r['strain'].get('stiffness_degradation',[])).size]
            print(sp,'PZT',len(rs),'label entries',len(labels),'cycles',len({str(r['cycles']) for r in labels}),'label examples',[r['strain'] for r in labels[:3]],flush=True)
if __name__=='__main__':
    if '--audit' in sys.argv:audit()
    else:main()
