"""Explicit device selection and relocatable checkpoint lookup."""
from pathlib import Path
import re


def select_device(torch, requested):
    mps = getattr(torch.backends, 'mps', None)
    if requested == 'auto':
        if torch.cuda.is_available():
            return 'cuda:0'
        if mps is not None and mps.is_available():
            return 'mps'
        return 'cpu'
    if requested == 'cpu':
        return requested
    if requested == 'mps':
        if mps is None or not mps.is_available():
            raise RuntimeError('MPS requested but unavailable. Check macOS/PyTorch support, or explicitly choose --device cpu.')
        return requested
    if re.fullmatch(r'cuda(?::[0-9]+)?', requested):
        index = int(requested.split(':')[1]) if ':' in requested else 0
        if not torch.cuda.is_available() or index >= torch.cuda.device_count():
            raise RuntimeError(f'{requested} requested but unavailable; no device substitution')
        return f'cuda:{index}'
    raise ValueError('device must be auto, cpu, mps or cuda:N')


def checkpoint(path):
    path = Path(path).expanduser().resolve()
    if not (path / 'config.json').is_file() or not any((path / name).is_file() for name in ('model.safetensors','pytorch_model.bin')):
        raise FileNotFoundError(f'Missing checkpoint config/weights: {path}')
    return str(path)


def model_locations(args, model_id, tokenizer_id, package_root):
    if args.models_dir and (args.model_path or args.tokenizer_path):
        raise ValueError('Use --models-dir or paired --model-path/--tokenizer-path, not both')
    if args.model_path or args.tokenizer_path:
        if not (args.model_path and args.tokenizer_path):
            raise ValueError('Both model and tokenizer paths are required')
        # Explicit Hub IDs remain supported; expand ~ only for actual user paths.
        return (str(Path(args.model_path).expanduser()) if args.model_path.startswith('~') else args.model_path,
                str(Path(args.tokenizer_path).expanduser()) if args.tokenizer_path.startswith('~') else args.tokenizer_path)
    bundled = Path(package_root) / 'models'
    if args.models_dir or (args.model == 'small' and bundled.exists()):
        root = Path(args.models_dir).expanduser() if args.models_dir else bundled
        return checkpoint(root / model_id.split('/')[-1]), checkpoint(root / tokenizer_id.split('/')[-1])
    return model_id, tokenizer_id
