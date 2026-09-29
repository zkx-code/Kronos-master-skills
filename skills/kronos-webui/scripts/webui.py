"""Launch the original Kronos Flask UI with explicit data and local model configuration."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request

SNAPSHOT=Path(__file__).resolve().parents[1]/'assets/kronos'


def read_model_mapping(path):
    path = Path(path).expanduser().resolve()
    mapping = json.loads(path.read_text(encoding='utf-8-sig'))
    for pair in mapping.values():
        for role in ('model', 'tokenizer'):
            location = Path(pair[role]).expanduser()
            pair[role] = str((location if location.is_absolute() else path.parent / location).resolve())
    return mapping


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(root):
    manifest=json.loads((SNAPSHOT/'source-manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        p=root/entry['path']
        if not p.is_file() or sha(p)!=entry['sha256']:
            raise ValueError(f'Original source differs or is missing: {p}')
    return len(manifest['files'])


def validate_data(path):
    import numpy as np
    import pandas as pd
    if path.suffix.lower()=='.csv': df=pd.read_csv(path)
    elif path.suffix.lower()=='.feather': df=pd.read_feather(path)
    else: raise ValueError('Only CSV/Feather is supported')
    if len(df)<520: raise ValueError('Original UI requires at least 400+120=520 rows')
    time_col=next((n for n in ('timestamps','timestamp','date') if n in df),None)
    if time_col is None: raise ValueError('Real timestamps required; generated timestamp fallback is not allowed')
    if pd.api.types.is_numeric_dtype(df[time_col]): raise ValueError('Convert epoch timestamp units explicitly first')
    times=pd.to_datetime(df[time_col],errors='raise')
    if times.isna().any() or times.duplicated().any() or not times.is_monotonic_increasing:
        raise ValueError('Timestamps must be complete, increasing and unique')
    if times.dt.tz is not None: raise ValueError('Convert to exchange-local naive timestamps before import')
    cols=['open','high','low','close']
    if not set(cols).issubset(df): raise ValueError('Missing OHLC columns')
    values=df[cols].apply(pd.to_numeric,errors='raise')
    if not np.isfinite(values.to_numpy()).all() or (values<=0).any().any(): raise ValueError('Invalid OHLC values')
    if (values.high<values[['open','close','low']].max(axis=1)).any() or (values.low>values[['open','close','high']].min(axis=1)).any():
        raise ValueError('Invalid OHLC relations')
    for col in ('volume','amount'):
        if col in df:
            x=pd.to_numeric(df[col],errors='raise')
            if not np.isfinite(x.to_numpy()).all() or (x<0).any(): raise ValueError(f'Invalid {col}')
    if df.isna().any().any(): raise ValueError('Missing values would be silently dropped by original UI; resolve source data first')
    return {'rows':len(df),'timestamp_column':time_col,'start':str(times.iloc[0]),'end':str(times.iloc[-1]),
            'regular_interval':bool(times.diff().iloc[1:].nunique()==1),'sha256':sha(path)}


def check(root):
    result={'source_files_verified':verify(root),'missing_imports':[], 'data_files':[],'issues':[]}
    for name in ('flask','flask_cors','plotly','numpy','pandas','torch','huggingface_hub','einops','safetensors','tqdm'):
        if importlib.util.find_spec(name) is None: result['missing_imports'].append(name)
    if not result['missing_imports']:
        for p in sorted((root/'data').glob('*')):
            if p.suffix in ('.csv','.feather'):
                try: result['data_files'].append({'path':str(p),**validate_data(p)})
                except Exception as exc: result['issues'].append(f'{p.name}: {exc}')
    result['status']='ready' if not result['missing_imports'] and not result['issues'] else 'requirements_missing'
    return result


def load_app(root,local_models=None,language='en'):
    if language not in ('zh','en'): raise ValueError('Language must be zh or en')
    verify(root)
    sys.path.insert(0,str(root))
    # Fail before importing app if real Kronos dependencies are unavailable.
    from model import Kronos, KronosTokenizer, KronosPredictor
    spec=importlib.util.spec_from_file_location('kronos_original_webapp',root/'webui/app.py')
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module)
    if not module.MODEL_AVAILABLE: raise RuntimeError('Original UI did not import the real model')
    if local_models:
        for key,pair in local_models.items():
            if key not in module.AVAILABLE_MODELS: raise ValueError(f'Unknown model key: {key}')
            for role in ('model','tokenizer'):
                p=Path(pair[role]).expanduser().resolve()
                if not (p/'config.json').is_file() or not any((p/n).is_file() for n in ('model.safetensors','pytorch_model.bin')):
                    raise ValueError(f'Missing checkpoint config/weights: {p}')
                module.AVAILABLE_MODELS[key][role+'_id']=str(p)
    # Wrapper validates input before the original loader can fabricate times/drop rows.
    from flask import request,jsonify
    from localization import localize_html,localize_payload
    def selected_language():
        value=request.args.get('lang') if request.path=='/' else None
        if value not in ('zh','en'): value=request.cookies.get('kronos_ui_language')
        return value if value in ('zh','en') else language
    @module.app.after_request
    def language_response(response):
        lang=selected_language()
        if request.path=='/' and response.status_code==200:
            response.set_data(localize_html(response.get_data(as_text=True),lang))
            response.set_cookie('kronos_ui_language',lang,samesite='Lax',httponly=True)
        elif response.is_json and lang=='zh':
            response.set_data(json.dumps(localize_payload(response.get_json()),ensure_ascii=False))
        response.headers['Content-Language']='zh-CN' if lang=='zh' else 'en'
        response.vary.add('Cookie')
        return response
    @module.app.before_request
    def validate_request():
        if request.path not in ('/api/load-data','/api/predict') or request.method!='POST': return None
        body=request.get_json(silent=True)
        if not isinstance(body,dict): return jsonify(error='Expected a JSON object'),400
        try:
            p=Path(body.get('file_path','')).resolve()
            if p.parent!=(root/'data').resolve(): raise ValueError('Select an imported file from this work directory data folder')
            validate_data(p)
        except Exception as exc: return jsonify(error=str(exc)),400
        return None
    return module


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    for name in ('stage','check','add-data','serve'):
        a=sub.add_parser(name); a.add_argument('--work-dir',type=Path,required=True)
        if name=='add-data': a.add_argument('--file',type=Path,required=True)
        if name=='serve':
            a.add_argument('--language',choices=['zh','en'],required=True,help='Ask the user Chinese or English before starting')
            a.add_argument('--port',type=int,default=7070)
            a.add_argument('--local-models',type=Path,help='JSON model-key -> {model: directory, tokenizer: directory}')
            a.add_argument('--cache-dir',type=Path)
    a=sub.add_parser('status'); a.add_argument('--port',type=int,default=7070)
    args=p.parse_args()
    if args.action=='status':
        with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/model-status',timeout=5) as r:
            print(r.read().decode('utf-8'))
        return 0
    root=args.work_dir.expanduser().resolve()
    if args.action=='stage':
        verify(SNAPSHOT)
        if root.exists(): raise FileExistsError('Choose a new work directory')
        shutil.copytree(SNAPSHOT,root); (root/'data').mkdir()
        print(json.dumps({'status':'staged','work_dir':str(root),'source_files':verify(root)})); return 0
    verify(root)
    if args.action=='add-data':
        source=args.file.resolve(); report=validate_data(source); target=root/'data'/source.name
        if target.exists(): raise FileExistsError(f'Data file already exists: {target}')
        shutil.copy2(source,target)
        report.update(source=str(source),destination=str(target))
        (root/'data'/f'{source.name}.import.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
    result=check(root); print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if result['status']!='ready': return 2
    if args.action=='check': return 0
    if not 1<=args.port<=65535: raise ValueError('Invalid port')
    cache=(args.cache_dir or root/'.cache').resolve(); os.environ['HF_HOME']=str(cache/'huggingface')
    os.environ['TORCH_HOME']=str(cache/'torch'); os.environ['PYTHONDONTWRITEBYTECODE']='1'
    mapping=read_model_mapping(args.local_models) if args.local_models else None
    module=load_app(root,mapping,args.language)
    runtime={'pid':os.getpid(),'host':'127.0.0.1','port':args.port,'debug':False,
             'cache_dir':str(cache),'local_models':mapping,'python':sys.executable,'language':args.language}
    (root/'webui-runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Open http://127.0.0.1:{args.port}; Ctrl+C stops this foreground server.',flush=True)
    module.app.run(host='127.0.0.1',port=args.port,debug=False,use_reloader=False,threaded=False)
    return 0


if __name__=='__main__': sys.exit(main())
