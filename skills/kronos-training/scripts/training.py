"""Stage, check and invoke the supplied Kronos training entry points unchanged."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import yaml

SNAPSHOT = Path(__file__).resolve().parents[1] / 'assets' / 'kronos'
PROFILES = ('qlib-preprocess','qlib-tokenizer','qlib-predictor','csv-sequential','csv-tokenizer','csv-predictor')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def plain(v):
    if isinstance(v, dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v, (list,tuple)): return [plain(x) for x in v]
    if isinstance(v, Path): return str(v)
    if hasattr(v,'isoformat'): return v.isoformat()
    if hasattr(v,'item'): return plain(v.item())
    return v


def write_json(path,obj):
    Path(path).write_text(json.dumps(plain(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def verify(root):
    manifest=json.loads((SNAPSHOT/'source-manifest.json').read_text(encoding='utf-8'))
    checked=[]
    for item in manifest['files']:
        path=root/item['path']
        if not path.is_file(): raise FileNotFoundError(f'Missing source file: {path}')
        actual=sha(path)
        configurable = item['path']=='finetune/config.py' or item['path'].startswith('finetune_csv/configs/')
        if actual != item['sha256'] and not (configurable and root.resolve()!=SNAPSHOT.resolve()):
            raise ValueError(f'Original training implementation changed: {item["path"]}')
        checked.append({'path':item['path'],'sha256':actual,'configured':actual!=item['sha256']})
    return {'source_root':manifest['source_root'],'files':checked}


def stage(args):
    verify(SNAPSHOT)
    target=args.work_dir.resolve()
    if target.exists(): raise FileExistsError(f'Choose a new work directory: {target}')
    shutil.copytree(SNAPSHOT,target)
    write_json(target/'stage.json',{'status':'staged','created_at':datetime.now().astimezone(),**verify(target)})
    print(json.dumps({'status':'staged','work_dir':str(target),'source_files':len(verify(target)['files'])},ensure_ascii=False))


def import_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def absolute(value, base):
    path=Path(os.path.expanduser(str(value)))
    return path.resolve() if path.is_absolute() else (base/path).resolve()


def check_qlib(args, root, profile, status):
    deps=['numpy','pandas','tqdm','qlib'] if profile=='qlib-preprocess' else ['torch','numpy','pandas','tqdm','einops','huggingface_hub','safetensors','comet_ml']
    status['missing_imports'] += [x for x in deps if importlib.util.find_spec(x) is None]
    cfg=import_module(root/'finetune/config.py','training_config').Config()
    base=root/'finetune'
    provider=absolute(cfg.qlib_data_path,base)
    status['inputs']['qlib_data_path']=str(provider)
    if profile=='qlib-preprocess' and not provider.is_dir(): status['issues'].append(f'Missing Qlib data directory: {provider}')
    dataset=absolute(cfg.dataset_path,base)
    status['inputs']['dataset_path']=str(dataset)
    if profile=='qlib-preprocess':
        status['outputs']['dataset_files']=[str(dataset/n) for n in ('train_data.pkl','val_data.pkl','test_data.pkl')]
        if dataset.exists() and any((dataset/n).exists() for n in ('train_data.pkl','val_data.pkl','test_data.pkl')):
            status['issues'].append(f'Preprocess would reuse/overwrite existing dataset files: {dataset}; choose new Config.dataset_path')
    else:
        for name in ('train_data.pkl','val_data.pkl'):
            path=dataset/name
            if not path.is_file(): status['issues'].append(f'Missing dataset: {path}')
        names=('pretrained_tokenizer_path',) if profile=='qlib-tokenizer' else ('finetuned_tokenizer_path','pretrained_predictor_path')
        for name in names:
            path=absolute(getattr(cfg,name),base); status['inputs'][name]=str(path)
            require_checkpoint(path,status)
        component=cfg.tokenizer_save_folder_name if profile=='qlib-tokenizer' else cfg.predictor_save_folder_name
        save=absolute(cfg.save_path,base)/component
        status['outputs']['checkpoint_targets']=[str(save/'checkpoints/best_model')]
        status['outputs']['training_directories']=[str(save)]
        if save.exists(): status['issues'].append(f'Training output exists: {save}')
        if os.name=='nt': status['issues'].append('Original Qlib training hardcodes CUDA/NCCL DDP; use a compatible Linux/WSL environment')
        if args.launcher=='python': status['issues'].append('Qlib training requires torchrun even for one GPU')
        device_check(status,True,0,args.nproc_per_node,'nccl')
        for name in ('epochs','batch_size','accumulation_steps','n_train_iter','n_val_iter'):
            if getattr(cfg,name,0)<1: status['issues'].append(f'{name} must be positive')
        if cfg.n_train_iter<cfg.batch_size*args.nproc_per_node:
            status['issues'].append('n_train_iter is too small for one distributed training batch')
    if getattr(cfg,'use_comet',False):
        status['issues'].append('Set Config.use_comet=False for this local launcher; original Comet uploads/logs the full config. Configure external tracking separately if explicitly requested')


def require_checkpoint(path,status):
    if not path.is_dir() or not (path/'config.json').is_file() or not any((path/n).is_file() for n in ('model.safetensors','pytorch_model.bin')):
        status['issues'].append(f'Missing local checkpoint config/weights: {path}; download the matching checkpoint explicitly first')


def device_check(status,use_cuda,device_id,workers,backend):
    if importlib.util.find_spec('torch') is None: return
    import torch
    if use_cuda:
        if not torch.cuda.is_available(): status['issues'].append('CUDA requested but unavailable; no automatic CPU fallback')
        elif device_id<0 or device_id>=torch.cuda.device_count() or workers>torch.cuda.device_count():
            status['issues'].append('Requested CUDA device/process count exceeds visible GPUs')
    if workers>1:
        if not use_cuda: status['issues'].append('Original CSV DDP initialization requires CUDA; CPU multi-process is not supported')
        if backend=='nccl' and not torch.distributed.is_nccl_available(): status['issues'].append('NCCL backend unavailable')


def load_yaml(path):
    with Path(path).open(encoding='utf-8') as f: return yaml.safe_load(f)


def check_csv(args, root, profile, status):
    deps=['torch','numpy','pandas','tqdm','yaml','einops','huggingface_hub','safetensors']
    status['missing_imports'] += [x for x in deps if importlib.util.find_spec(x) is None]
    if not args.config: status['issues'].append('--config is required for CSV profiles'); return
    cfg_path=args.config.resolve()
    if not cfg_path.is_file(): status['issues'].append(f'Missing YAML config: {cfg_path}'); return
    loader=import_module(root/'finetune_csv/config_loader.py','original_csv_config')
    original=loader.CustomFinetuneConfig(str(cfg_path))
    cfg=original.loader.config; data=cfg.get('data',{}); paths=cfg.get('model_paths',{}); exp=cfg.get('experiment',{})
    base=root/'finetune_csv'
    data_path=absolute(data.get('data_path',''),base)
    status['inputs']['data_path']=str(data_path)
    if not data_path.is_file(): status['issues'].append(f'Missing CSV training data: {data_path}')
    else:
        import pandas as pd
        import numpy as np
        frame=pd.read_csv(data_path)
        required={'timestamps','open','high','low','close','volume','amount'}
        missing=sorted(required-set(frame.columns))
        if missing: status['issues'].append(f'CSV missing columns: {missing}')
        else:
            times=pd.to_datetime(frame.timestamps,errors='raise')
            if times.isna().any() or times.duplicated().any() or not times.is_monotonic_increasing:
                status['issues'].append('CSV timestamps must be unique, nonmissing and increasing')
            cols=['open','high','low','close','volume','amount']; x=frame[cols].apply(pd.to_numeric,errors='raise')
            if not np.isfinite(x.to_numpy()).all() or (x[cols[:4]]<=0).any().any() or (x[cols[4:]]<0).any().any() or (x.high<x[['open','close','low']].max(axis=1)).any() or (x.low>x[['open','close','high']].min(axis=1)).any():
                status['issues'].append('CSV contains invalid OHLCVA values')
            n=len(frame); train_end=int(n*original.train_ratio); val_end=int(n*(original.train_ratio+original.val_ratio))
            window=original.lookback_window+original.predict_window+1
            sizes={'train':train_end,'val':val_end-train_end,'test':n-val_end}
            status['data_audit']={'rows':n,'sha256':sha(data_path),'split_rows':sizes,'window':window}
            for split in ('train','val'):
                if sizes[split]<=window: status['issues'].append(f'{split} split must contain more than {window} rows (original dataset requirement)')
            samples=train_end-window+1
            if samples<original.batch_size*args.nproc_per_node: status['issues'].append('Training split too short for one full batch per process (drop_last=True)')
    selected=[]
    if profile=='csv-tokenizer' or (profile=='csv-sequential' and original.train_tokenizer and not args.skip_tokenizer): selected.append('tokenizer')
    if profile=='csv-predictor' or (profile=='csv-sequential' and original.train_basemodel and not args.skip_basemodel): selected.append('predictor')
    if not selected: status['issues'].append('No training stage selected')
    status['stages']=selected
    if not original.pre_trained_tokenizer or not original.pre_trained_predictor:
        status['issues'].append('This fine-tuning launcher requires pretrained flags true; random initialization is a separate experiment')
    targets={'tokenizer':absolute(original.tokenizer_best_model_path,base),'predictor':absolute(original.basemodel_best_model_path,base)}
    dirs={'tokenizer':absolute(original.tokenizer_save_path,base),'predictor':absolute(original.basemodel_save_path,base)}
    skip=profile=='csv-sequential' and (args.skip_existing or original.skip_existing)
    reused=[]
    for stage_name in selected:
        if dirs[stage_name].exists():
            if skip and targets[stage_name].is_dir():
                require_checkpoint(targets[stage_name],status); reused.append(stage_name)
            elif any(dirs[stage_name].iterdir()): status['issues'].append(f'Nonempty training output: {dirs[stage_name]}; use a new path or explicit skip-existing')
    active=[s for s in selected if s not in reused]
    status['reused_stages']=reused
    if 'tokenizer' in active: require_checkpoint(absolute(original.pretrained_tokenizer_path,base),status)
    if 'predictor' in active:
        require_checkpoint(absolute(original.pretrained_predictor_path,base),status)
        input_tok=absolute(original.finetuned_tokenizer_path,base)
        if 'tokenizer' not in active: require_checkpoint(input_tok,status)
        elif input_tok!=targets['tokenizer']: status['issues'].append('Sequential Predictor tokenizer path must match the Tokenizer output')
    status['outputs']['checkpoint_targets']=[str(targets[s]) for s in selected]
    status['outputs']['training_directories']=[str(dirs[s]) for s in selected]
    status['outputs']['base_save_path']=str(absolute(original.base_save_path,base))
    for name in ('batch_size','accumulation_steps','tokenizer_epochs','basemodel_epochs'):
        if getattr(original,name)<1: status['issues'].append(f'{name} must be positive')
    if original.num_workers<0: status['issues'].append('num_workers must be nonnegative')
    backend=os.environ.get('DIST_BACKEND','nccl')
    if profile!='csv-sequential' and args.launcher=='torchrun': status['issues'].append('Original standalone CSV mains do not initialize DDP; use csv-sequential with skip flags')
    if profile!='csv-sequential':
        status['notes'].append('Original standalone CSV scripts auto-select CUDA/CPU and ignore YAML device selection; prefer sequential with skip flags for controlled device selection')
    device_check(status,original.use_cuda,original.device_id,args.nproc_per_node,backend)
    ratios=[float(data.get(x,0)) for x in ('train_ratio','val_ratio','test_ratio')]
    if any(not math.isfinite(x) or x<0 for x in ratios) or abs(sum(ratios)-1)>1e-6: status['issues'].append(f'Split ratios must sum to 1: {ratios}')
    lookback=int(data.get('lookback_window',0)); pred=int(data.get('predict_window',0)); maxctx=int(data.get('max_context',0))
    if not 2<=lookback<=maxctx: status['issues'].append(f'lookback_window must be between 2 and max_context: {lookback}/{maxctx}')
    if not 1<=pred<=maxctx: status['issues'].append(f'predict_window must be between 1 and max_context: {pred}/{maxctx}')
    if exp.get('use_comet',False): status['issues'].append('experiment.use_comet is true; provide credentials through environment or set false in the work copy')


def check(args):
    root=args.work_dir.resolve(); status={'status':'ready','profile':args.profile,'work_dir':str(root),'python':sys.executable,'missing_imports':[],'issues':[],'inputs':{},'outputs':{},'notes':[]}
    status['source_verification']=verify(root)
    if args.nproc_per_node<1: status['issues'].append('nproc-per-node must be positive')
    if args.nproc_per_node>1 and (args.launcher=='python' or (args.launcher=='auto' and args.profile.startswith('csv'))):
        status['issues'].append('Multiple CSV processes require explicit launcher=torchrun')
    if args.profile=='qlib-preprocess' and args.launcher=='torchrun':
        status['issues'].append('Preprocessing is a single Python process, not a distributed training stage')
    if args.profile!='csv-sequential' and (args.skip_existing or args.skip_tokenizer or args.skip_basemodel): status['issues'].append('skip flags only apply to csv-sequential')
    try:
        if args.profile.startswith('qlib'): check_qlib(args,root,args.profile,status)
        else: check_csv(args,root,args.profile,status)
    except (ValueError,TypeError,KeyError,AttributeError,FileNotFoundError) as exc:
        status['issues'].append(f'Invalid configuration or input: {exc}')
    if status['missing_imports'] or status['issues']: status['status']='requirements_missing'
    return status


def command_for(args,root):
    py=[sys.executable,'-X','utf8','-B','-u']
    if args.launcher=='torchrun' or (args.launcher=='auto' and args.profile in ('qlib-tokenizer','qlib-predictor')):
        py=[sys.executable,'-X','utf8','-B','-u','-m','torch.distributed.run','--standalone',f'--nproc_per_node={args.nproc_per_node}']
    if args.profile=='qlib-preprocess': return py+['qlib_data_preprocess.py'],root/'finetune'
    if args.profile=='qlib-tokenizer': return py+['train_tokenizer.py'],root/'finetune'
    if args.profile=='qlib-predictor': return py+['train_predictor.py'],root/'finetune'
    if not args.config: raise ValueError('--config is required')
    script={'csv-sequential':'train_sequential.py','csv-tokenizer':'finetune_tokenizer.py','csv-predictor':'finetune_base_model.py'}[args.profile]
    cmd=py+[script,'--config',str(args.config.resolve())]
    if args.profile=='csv-sequential':
        if args.skip_existing: cmd.append('--skip-existing')
        if args.skip_tokenizer: cmd.append('--skip-tokenizer')
        if args.skip_basemodel: cmd.append('--skip-basemodel')
    return cmd,root/'finetune_csv'


def run(args):
    status=check(args)
    if status['status']!='ready': print(json.dumps(status,ensure_ascii=False,indent=2)); return 2
    if args.output_dir is None: raise ValueError('--output-dir is required for run')
    out=args.output_dir.resolve()
    if out.exists(): raise FileExistsError(f'Choose a new output directory: {out}')
    out.mkdir(parents=True)
    record={'status':'running','started_at':datetime.now().astimezone(),'profile':args.profile,'arguments':vars(args).copy(),'check':status}
    record['arguments'].pop('handler',None)
    # Snapshot only the configuration for this profile; redact credential-like fields in YAML.
    if args.profile.startswith('csv'):
        def redact(obj):
            if isinstance(obj,dict): return {k:('[REDACTED]' if any(s in str(k).lower() for s in ('api_key','password','secret','access_token')) else redact(v)) for k,v in obj.items()}
            if isinstance(obj,list): return [redact(v) for v in obj]
            return obj
        (out/'config.snapshot.yaml').write_text(yaml.safe_dump(redact(load_yaml(args.config)),allow_unicode=True),encoding='utf-8')
        record['config_sha256']=sha(args.config)
    else:
        record['config_sha256']=sha(args.work_dir/'finetune/config.py')
    cmd,cwd=command_for(args,args.work_dir.resolve())
    record['command']=cmd; record['cwd']=str(cwd)
    write_json(out/'run.json',record)
    env=os.environ.copy(); env['MPLBACKEND']='Agg'; env['PYTHONDONTWRITEBYTECODE']='1'
    try:
        with (out/'run.log').open('w',encoding='utf-8') as log:
            proc=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
        if proc.returncode: raise RuntimeError(f'Original training script failed with exit code {proc.returncode}; inspect run.log')
        if args.profile=='qlib-preprocess':
            for path in status['outputs']['dataset_files']:
                if not Path(path).is_file() or Path(path).stat().st_size==0: raise RuntimeError(f'Missing preprocessing output: {path}')
        else:
            audit={'issues':[]}
            for path in status['outputs']['checkpoint_targets']: require_checkpoint(Path(path),audit)
            if audit['issues']: raise RuntimeError('; '.join(audit['issues']))
            record['checkpoints']=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for folder in status['outputs']['checkpoint_targets'] for p in Path(folder).iterdir() if p.is_file()]
        record['status']='complete'
    except Exception as e:
        record['status']='failed'; record['error']=str(e)
        with (out/'run.log').open('a',encoding='utf-8') as log: traceback.print_exc(file=log)
    record['finished_at']=datetime.now().astimezone(); write_json(out/'run.json',record)
    print(json.dumps({'status':record['status'],'output_dir':str(out),'run_log':str(out/'run.log')},ensure_ascii=False))
    return 0 if record['status']=='complete' else 1


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    st=sub.add_parser('stage'); st.add_argument('--work-dir',type=Path,required=True)
    vf=sub.add_parser('verify'); vf.add_argument('--work-dir',type=Path,required=True)
    for action in ('check','run'):
        q=sub.add_parser(action); q.add_argument('--profile',choices=PROFILES,required=True); q.add_argument('--work-dir',type=Path,required=True); q.add_argument('--config',type=Path); q.add_argument('--output-dir',type=Path)
        q.add_argument('--skip-existing',action='store_true'); q.add_argument('--skip-tokenizer',action='store_true'); q.add_argument('--skip-basemodel',action='store_true')
        q.add_argument('--launcher',choices=['auto','python','torchrun'],default='auto')
        q.add_argument('--nproc-per-node',type=int,default=1)
    a=p.parse_args()
    if a.action=='stage': stage(a); return 0
    if a.action=='verify': print(json.dumps(verify(a.work_dir.resolve()),ensure_ascii=False,indent=2)); return 0
    if a.action=='check':
        result=check(a); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['status']=='ready' else 2
    return run(a)


if __name__=='__main__': sys.exit(main())
