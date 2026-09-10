"""Recreate this project's private runtime. Run with an existing Python 3.12."""
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
ASSETS = [
    ('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip',
     'tools/realesrgan-ncnn-vulkan-20220424-windows.zip',
     'abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d', 'tools/realesrgan'),
    ('https://github.com/denoland/deno/releases/download/v2.9.6/deno-x86_64-pc-windows-msvc.zip',
     'tools/deno.zip', '15e5300b0ba3c3695a7621d90160a746ec9e710228cee639afa9d580f6e3cd11', 'tools/deno'),
    ('https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml',
     'models/lbpcascade_animeface.xml', '9376d30ac38db6bda2a68b88b3b76bbd7e6aa33af47f7f5c76bc88ca75f1ce30', None)
]


def main():
    if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64') or sys.maxsize <= 2**32:
        raise SystemExit('此安装脚本面向 Windows x64 与 64-bit Python。')
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('此版本使用锁定的 Python 3.12 依赖。请用 py -3.12 setup.py 或 Python 3.12 运行。')
    for name in ('ffmpeg', 'ffprobe'):
        if not shutil.which(name):
            raise SystemExit(f'需要先安装 {name} 并加入 PATH；本脚本不修改系统工具。')
    for name in ('input', 'video', 'frames', 'output', 'models', 'tools', 'tests'):
        (ROOT / name).mkdir(exist_ok=True)
    records = []
    for url, rel, expected, target in ASSETS:
        p = ROOT / rel
        if not p.exists():
            request = urllib.request.Request(url, headers={'User-Agent': 'anime-enhance-setup'})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError(f'下载内容与固定版本哈希不符: {url}')
            with p.open('xb') as f:
                f.write(data)
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f'本地文件哈希不符，请人工检查，不自动覆盖: {p}')
        if target:
            dest = ROOT / target
            with zipfile.ZipFile(p) as archive:
                for member in archive.infolist():
                    output = (dest / member.filename).resolve()
                    if not output.is_relative_to(dest.resolve()):
                        raise ValueError('ZIP 包含目录越界路径')
                    if member.is_dir():
                        output.mkdir(parents=True, exist_ok=True)
                    elif not output.exists():
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with output.open('xb') as f:
                            f.write(archive.read(member))
        records.append({'url': url, 'path': rel, 'sha256': actual})
    for src in (ROOT / 'tools/realesrgan/models').glob('*'):
        target = ROOT / 'models' / src.name
        if src.is_file() and not target.exists():
            shutil.copy2(src, target)
    python = ROOT / 'tools/venv/Scripts/python.exe'
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', ROOT / 'tools/venv'], check=True)
    subprocess.run([python, '-m', 'pip', 'install', '-r', ROOT / 'requirements-lock.txt'], check=True)
    (ROOT / 'tools/installed-assets.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    subprocess.run([python, ROOT / 'workflow.py', 'doctor'], check=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    main()
