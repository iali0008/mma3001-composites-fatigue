from inspect_sources import *
import csv,re,zipfile
def save_csv(name,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def run():
    pzt=json.loads((OUT/'pzt_metadata.json').read_text())
    strain=json.loads((OUT/'strain_profile.json').read_text())
    groups=collections.defaultdict(list);overview=[];allfiles=[];conflicts=[];notes=[]
    scalar=lambda v:isinstance(v,(int,float)) and np.isfinite(v)
    for r in pzt:
        if 'error' in r:continue
        v=r['strain'].get('stiffness_degradation',[])
        if scalar(v):groups[(r['specimen'],r['cycles'])].append(r)
    for lay in sorted(SRC.glob('Layup[123]')):
        for sp in sorted(lay.glob('L*_F')):
            prs=[r for r in pzt if r['specimen']==sp.name]
            mats=[r for r in strain if r['specimen']==sp.name]
            types=collections.Counter()
            for p in sorted(sp.rglob('*')):
                if not p.is_file() or p.name.startswith('.') or not ('strain' in str(p.parent).lower()):continue
                if p.suffix=='.m':continue
                with p.open('rb') as f:head=f.read(650)
                if p.suffix=='.mat':typ='converted_mat'
                elif b'Load, Extensometer, Displacement' in head:typ='mts_binary'
                else:
                    try:
                        a=np.loadtxt(p);typ='numeric_text'
                        if a.ndim!=2 or a.shape[1]!=7:typ='text_other_shape'
                    except Exception:typ='other'
                types[typ]+=1;allfiles.append(dict(specimen=sp.name,path=str(p.relative_to(SRC)),kind=typ,bytes=p.stat().st_size))
            rs=[r for r in prs if scalar(r.get('strain',{}).get('stiffness_degradation'))]
            zeros=[r for r in prs if isinstance(r.get('strain',{}).get('stiffness_degradation'),list) and len(r['strain']['stiffness_degradation']) and not np.any(r['strain']['stiffness_degradation'])]
            overview.append(dict(layup=lay.name,specimen=sp.name,pzt_files=len(prs),pzt_cycles=len({str(r.get('cycles')) for r in prs}),scalar_label_files=len(rs),scalar_checkpoints=len({r['cycles'] for r in rs}),positive_checkpoints=len({r['cycles'] for r in rs if r['strain']['stiffness_degradation']>0}),zero_vector_files=len(zeros),empty_label_files=sum(np.asarray(r.get('strain',{}).get('stiffness_degradation',[])).size==0 for r in prs),strain_mat=len(mats),strain_binary=types['mts_binary'],strain_numeric_text=types['numeric_text']))
            books=[p for p in sp.glob('*.xlsx') if not p.name.startswith('.')]
            for p in books:
                w=load_workbook(p,data_only=True)
                for s in w:
                    if not s.title.lower().startswith('log'):continue
                    for row in s.iter_rows():
                        v=[c.value for c in row]
                        if len(v)<9:continue
                        if v[8]:notes.append(dict(specimen=sp.name,sheet=s.title,row=row[0].row,cycle=v[3],pzt=v[6],mts=v[7],remark=v[8]))
                        if not isinstance(v[6],str):continue
                        name=v[6].strip(" '\"")
                        rr=[r for r in prs if r['file']==name]
                        if len(rr)!=1:continue
                        r=rr[0]
                        if scalar(v[3]) and v[3]!=r.get('cycles'):conflicts.append(dict(specimen=sp.name,file=name,kind='cycle',logbook=v[3],matlab=r.get('cycles'),row=row[0].row))
                        if scalar(v[4]) and scalar(r.get('load')) and abs(v[4]-r['load'])>1e-8:conflicts.append(dict(specimen=sp.name,file=name,kind='load',logbook=v[4],matlab=r.get('load'),row=row[0].row))
    labels=[]
    for (sp,cy),rs in sorted(groups.items()):
        vals=sorted(set(r['strain']['stiffness_degradation'] for r in rs))
        refs=[]
        for r in rs:
            loc=r['strain'].get('file_location',[])
            refs.extend([loc] if isinstance(loc,str) else loc)
        refs=sorted(set(refs))
        folder=SRC/rs[0]['layup']/sp/'StrainData'
        found=[];missing=[]
        for ref in refs:
            candidates=[folder/ref,folder/(ref+'.mat')]
            hits=[p for p in candidates if p.exists()]
            (found if hits else missing).append(ref)
        status='published_scalar_candidate'
        if vals[0]<0:status='flag_negative'
        if cy==0:status='baseline_reference_only'
        labels.append(dict(layup=rs[0]['layup'],specimen=sp,cycles=cy,stiffness_degradation=vals[0],status=status,pzt_repeats=len(rs),distinct_values=len(vals),conditions=';'.join(sorted({r['condition'] for r in rs})),referenced_strain_files=len(refs),resolved_strain_files=len(found),missing_refs=';'.join(missing),reference_files=';'.join(found),source_pzt_files=';'.join(r['file'] for r in rs)))
    save_csv('specimen_summary.csv',overview);save_csv('label_checkpoints.csv',labels)
    save_csv('strain_inventory.csv',allfiles);save_csv('logbook_remarks.csv',notes);save_csv('metadata_conflicts.csv',conflicts)
    channels=[]
    for r in strain:
        for k,v in r['fields'].items():channels.append(dict(specimen=r['specimen'],file=r['file'],channel=k,**{x:y for x,y in v.items() if x!='shape'}))
    save_csv('strain_channels.csv',channels)
    before=json.loads((OUT/'original_manifest.json').read_text())
    changed=[]
    for r in before:
        p=SRC/r['path']
        if not p.exists() or p.stat().st_size!=r['size'] or p.stat().st_mtime_ns!=r['mtime_ns']:changed.append(r['path'])
    integrity=dict(files_checked=len(before),changed_size_or_mtime=changed,method='Compare source file presence, sizes and last-write timestamps to pre-analysis manifest; not a cryptographic before/after comparison.')
    (OUT/'source_integrity.json').write_text(json.dumps(integrity,indent=2))
    print(json.dumps(overview,indent=2));print('CHECKPOINTS',len(labels),'CONFLICTS',len(conflicts),'INTEGRITY',integrity)
    print('Strain field schemas',dict(collections.Counter(tuple(r['fields']) for r in strain)))
    print('All paths counts',dict(collections.Counter(r.get('path_count') for r in pzt)))
    print('Missing label references',[(r['specimen'],r['cycles'],r['missing_refs']) for r in labels if r['missing_refs']])
def notebook():
    import io,contextlib
    sources=[
'''from pathlib import Path
import json
import pandas as pd
audit = Path.cwd() if (Path.cwd() / 'specimen_summary.csv').exists() else Path.cwd() / 'audit_stiffness'
summary = pd.read_csv(audit / 'specimen_summary.csv')
labels = pd.read_csv(audit / 'label_checkpoints.csv')
channels = pd.read_csv(audit / 'strain_channels.csv')
metadata = json.loads((audit / 'pzt_metadata.json').read_text())
assert summary.pzt_files.sum() == 1495
assert summary.strain_mat.sum() == 317
assert len(labels) == 39
assert not labels.duplicated(['specimen', 'cycles']).any()
assert labels.distinct_values.eq(1).all()
assert labels.referenced_strain_files.eq(labels.resolved_strain_files).all()
assert channels.finite.eq(channels.n).all()
assert all(r['path_count'] == 252 for r in metadata)
print(summary.groupby('layup')[['pzt_files','scalar_checkpoints','positive_checkpoints']].sum().to_string())
''',
'''print(labels[['specimen','cycles','stiffness_degradation','status']].to_string(index=False))
assert labels.stiffness_degradation.gt(0).sum() == 35
assert labels.stiffness_degradation.eq(0).sum() == 3
assert labels.stiffness_degradation.lt(0).sum() == 1
assert summary.scalar_label_files.sum() == 255
assert summary.zero_vector_files.sum() == 49
assert summary.empty_label_files.sum() == 1191
print('39 checkpoint candidates = 35 positive + 3 baseline references + 1 negative flag.')
print('These counts do not establish independent mechanical validation.')
''',
'''# Independently transcribed from the supplied Technical Report, Appendix A.
reference = {
 'L1_S11_F': ([0,1,10,100,1000,10000,20000,30000,40000,50000,60000,70000,80000,90000,100000],
 [0,.055036381,.045813245,.060735707,.069766198,.076005931,.098380137,.10051699,.11226211,.118553783,.10426744,.128221136,.12236086,.11445585,.120155531]),
 'L1_S12_F': ([0,1,10,100,1000,10000,30000,40000,50000,60000,70000,80000,90000,100000],
 [0,.043288345,.051679586,.047985147,.059726484,.084112497,.233175942,.239071597,.236134709,.245338988,.244799668,.237792304,.245462847,.245730332]),
 'L2_S11_F': ([0,1,10,100,1000,10000,20000,30000,40000,50000,60000],
 [0,-.012213572,.012154654,.005044283,.008583815,.010634185,.031656763,.042811126,.055037786,.044292129,.084180661])}
for specimen, (cycles, values) in reference.items():
    expected = dict(zip(cycles, values))
    actual = labels[labels.specimen.eq(specimen)]
    assert all(abs(row.stiffness_degradation-expected[row.cycles]) < 1e-12 for row in actual.itertuples())
    print(specimen, 'matching checkpoints:',len(actual), 'documented cycles missing in actual labels:', sorted(set(cycles)-set(actual.cycles)))
''',
'''conflicts = pd.read_csv(audit / 'metadata_conflicts.csv')
print(conflicts.groupby(['specimen','kind']).size().to_string())
bad = channels[(channels.specimen.eq('L3_S11_F')) & (channels.file.eq('L3_S11_F08_DAT.mat')) & channels.channel.eq('strain1')]
assert len(bad)==1 and bad.iloc[0]['min']==bad.iloc[0]['max'] and bad.iloc[0]['n']==92550
print('Confirmed constant L3S11 F08 channel 1:', bad[['n','min','max']].to_string(index=False))
integrity = json.loads((audit / 'source_integrity.json').read_text())
assert integrity['changed_size_or_mtime'] == []
print('Source files with unchanged size and last-write timestamp:',integrity['files_checked'])
'''
    ]
    cells=[dict(cell_type='markdown',metadata={},source=['# Stiffness-label feasibility audit\n','Recorded evidence review. Run from the workspace root or audit_stiffness. See ASSESSMENT.md for interpretation and source limitations.\n','The extraction scripts read originals and write only audit outputs. This notebook verifies the cached audit, not a new raw-data extraction.'])]
    ns={}
    for i,source in enumerate(sources,1):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):exec(source,ns)
        cells.append(dict(cell_type='code',execution_count=i,metadata={},source=source.splitlines(True),outputs=[dict(output_type='stream',name='stdout',text=stream.getvalue().splitlines(True))]))
    nb=dict(cells=cells,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3'),language_info=dict(name='python',version='3.13')),nbformat=4,nbformat_minor=5)
    (OUT/'audit_review.ipynb').write_text(json.dumps(nb,indent=2),encoding='utf-8')
    print('Notebook checks passed; saved audit_review.ipynb')
if __name__=='__main__':
    if not (OUT/'specimen_summary.csv').exists():run()
    notebook()
