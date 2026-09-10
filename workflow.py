"""Local anime super-resolution and timestamp-aware video frame extraction."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
if (ROOT / 'config.local.json').is_file():
    for key, value in json.loads((ROOT / 'config.local.json').read_text(encoding='utf-8')).items():
        if isinstance(value, dict) and isinstance(CONFIG.get(key), dict):
            CONFIG[key].update(value)
        else:
            CONFIG[key] = value
LEVELS = {'保真': 'faithful', '清晰': 'clear', '超清': 'ultra',
          'faithful': 'faithful', 'clear': 'clear', 'ultra': 'ultra'}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def job_dir(folder, name):
    safe = re.sub(r'[^\w.-]+', '_', name)[:60]
    p = ROOT / folder / f'{datetime.now():%Y%m%d-%H%M%S}_{safe}_{uuid.uuid4().hex[:8]}'
    p.mkdir(parents=True, exist_ok=False)
    return p


def tool(name):
    value = CONFIG['tools'].get(name, name)
    p = ROOT / value
    if p.is_file():
        return str(p.resolve())
    found = shutil.which(value)
    if found:
        return found
    raise RuntimeError(f'工具不存在: {name}: {value}')


def run(args, log=None, timeout=1800):
    args = [str(a) for a in args]
    result = subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace',
                            timeout=timeout, cwd=ROOT,
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    if log:
        Path(log).write_text(json.dumps(args, ensure_ascii=False) + '\n' + result.stderr + result.stdout,
                             encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'命令失败 ({result.returncode}): {args[0]}\n{result.stderr[-3000:]}')
    return result.stdout


def seconds(value):
    text = str(value).strip()
    match = re.fullmatch(r'(?:(\d+)小时)?(?:(\d+)分(?:钟)?)?(\d+(?:\.\d+)?)?秒?', text)
    if match and any(match.groups()) and any(c in text for c in '小时分秒'):
        h, m, s = match.groups()
        total = float(h or 0) * 3600 + float(m or 0) * 60 + float(s or 0)
    else:
        parts = text.split(':')
        if not 1 <= len(parts) <= 3:
            raise ValueError('时间格式应为 92.417、01:32.417 或 1分32.417秒')
        nums = [float(x) for x in parts]
        if any(x < 0 or not math.isfinite(x) for x in nums) or any(x >= 60 for x in nums[1:]):
            raise ValueError('无效时间')
        total = sum(x * 60 ** i for i, x in enumerate(reversed(nums)))
    if not math.isfinite(total) or total < 0:
        raise ValueError('时间必须为非负有限数')
    return total


def enhance(source, level='faithful', scale=None, gpu=None):
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
        raise ValueError('支持 PNG、JPG、JPEG、WebP')
    level = LEVELS[level]
    scale = scale or (4 if level == 'ultra' else 2)
    if scale not in (2, 4) or (level == 'ultra' and scale != 4):
        raise ValueError('仅支持 2×/4×；超清固定为 4×')
    original_hash = digest(source)
    with source.open('rb') as f:
        header = f.read(25)
    with Image.open(source) as im:
        if getattr(im, 'n_frames', 1) > 1:
            raise ValueError('动态图请先指定帧；不会静默只处理第一帧')
        if im.mode.startswith('I') or im.mode == 'F' or (header.startswith(b'\x89PNG\r\n\x1a\n') and header[24] == 16):
            raise ValueError('此 NCNN 流程支持 8-bit SDR 图片；16-bit 图片请先明确转换策略')
        if im.width * im.height * 16 > CONFIG['max_native_output_pixels']:
            raise ValueError('原生 4× 中间图超过内存保护阈值；请先检查尺寸与 config.json')
        info = dict(im.info)
        src = ImageOps.exif_transpose(im).copy()
    has_alpha = 'A' in src.getbands() or 'transparency' in info
    rgba = src.convert('RGBA') if has_alpha else None
    rgb = src.convert('RGB')
    w, h = rgb.size
    if w * h * 16 > CONFIG['max_native_output_pixels']:
        raise ValueError('原生 4× 中间图超过本机内存保护阈值；请先检查尺寸并调整 config.json')
    target = (w * scale, h * scale)
    out = job_dir('output', source.stem)
    work = out / 'work'
    work.mkdir()
    rgb.save(work / 'input_rgb.png')
    start = time.monotonic()
    cmd = [tool('realesrgan'), '-i', work / 'input_rgb.png', '-o', work / 'native_x4.png',
           '-m', ROOT / 'models', '-n', 'realesrgan-x4plus-anime', '-s', '4',
           '-t', str(CONFIG['tile_size']),
           '-j', '1:1:1', '-f', 'png']
    device = CONFIG['gpu_id'] if gpu is None else gpu
    if device is not None:
        cmd += ['-g', str(device)]
    run(cmd, out / 'inference.log')
    with Image.open(work / 'native_x4.png') as im:
        if im.size != (w * 4, h * 4):
            raise RuntimeError(f'模型输出尺寸异常: {im.size}')
        sr = im.convert('RGB')
    if scale == 2:
        sr = sr.resize(target, Image.Resampling.LANCZOS)
    # No face restoration, inpainting, geometry edits, or generative redraw.
    baseline = rgb.resize(target, Image.Resampling.LANCZOS)
    weight = CONFIG['sr_mix'][level]
    result = Image.blend(baseline, sr, weight)
    if level == 'clear':
        result = result.filter(ImageFilter.UnsharpMask(radius=0.65, percent=12, threshold=4))
    if has_alpha:
        # Alpha never enters the neural network. Bilinear avoids ringing/negative alpha.
        alpha = rgba.getchannel('A').resize(target, Image.Resampling.BILINEAR)
        result.putalpha(alpha)
    filename = out / f'{source.stem}_{level}_{scale}x.png'
    metadata = {k: info[k] for k in ('icc_profile', 'dpi') if info.get(k)}
    result.save(filename, **metadata)
    with Image.open(filename) as verify:
        verify.load()
        if verify.size != target or (has_alpha and verify.mode != 'RGBA'):
            raise RuntimeError('尺寸或透明通道验证失败')
    if digest(source) != original_hash:
        raise RuntimeError('源文件哈希发生变化')
    manifest = {'source': str(source), 'source_sha256': original_hash, 'output': str(filename),
                'output_sha256': digest(filename), 'source_size': [w, h], 'output_size': list(target),
                'level': level, 'scale': scale, 'model': 'realesrgan-x4plus-anime',
                'model_sha256': digest(ROOT / 'models/realesrgan-x4plus-anime.bin'),
                'native_scale': 4, 'sr_mix': weight, 'alpha_preserved': has_alpha,
                'alpha_method': 'original alpha resized with bilinear' if has_alpha else None,
                'seconds': round(time.monotonic() - start, 3), 'generative_redraw': False,
                'face_restoration': False, 'source_unchanged': True,
                'limitation': '学习型超分会估计细节；不能保证细节逐像素不变。'}
    write_json(out / 'result.json', manifest)
    # Only remove our two known temporary files, never source/user files.
    for name in ('input_rgb.png', 'native_x4.png'):
        (work / name).unlink()
    work.rmdir()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def ytdlp_base():
    base = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
            '--socket-timeout', '25', '--retries', '2', '--no-progress',
            '--ffmpeg-location', tool('ffmpeg')]
    deno = ROOT / 'tools/deno/deno.exe'
    if deno.is_file():
        base += ['--js-runtimes', f'deno:{deno}']
    return base


def inspect_url(url, folder):
    if not re.match(r'^https?://', url):
        raise ValueError('必须提供公开 HTTP(S) URL')
    info = json.loads(run(ytdlp_base() + ['--skip-download', '--dump-single-json', url], folder / 'probe.log'))
    if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming'):
        raise ValueError('请提供已发布的非直播视频')
    if info.get('availability') not in (None, 'public', 'unlisted'):
        raise ValueError('该视频需要登录/购买或存在其他访问限制；不会绕过')
    formats = [f for f in info.get('formats', []) if f.get('vcodec') not in (None, 'none') and not f.get('has_drm')]
    if info.get('has_drm') or not formats:
        raise ValueError('没有可公开获取的非 DRM 视频格式')
    return info, formats


def download(url):
    folder = job_dir('video', 'download')
    info, formats = inspect_url(url, folder)
    # Video only: no re-encoding, no need to download audio for frame extraction.
    cmd = ytdlp_base() + ['-f', 'bv/b', '-S', 'res,fps,br', '--write-info-json',
                         '--no-overwrites', '-o', str(folder / '%(id)s.%(ext)s'),
                         '--print', 'after_move:filepath', url]
    result = run(cmd, folder / 'download.log')
    paths = [Path(s.strip()) for s in result.splitlines() if s.strip()]
    media = next((p for p in reversed(paths) if p.is_file() and p.suffix not in ('.json', '.log')), None)
    if media is None:
        raise RuntimeError('下载结束但没有有效视频文件；查看 download.log')
    meta = next(folder.glob('*.info.json'))
    selected = json.loads(meta.read_text(encoding='utf-8'))
    fields = ('format_id', 'width', 'height', 'fps', 'vcodec', 'tbr', 'dynamic_range')
    manifest = {'url': url, 'title': info.get('title'), 'uploader': info.get('uploader'),
                'channel_id': info.get('channel_id'), 'channel_url': info.get('channel_url'),
                'official_channel_verified': info.get('channel_id') in CONFIG['official_channels'],
                'path': str(media), 'sha256': digest(media),
                'quality_scope': '最高公开可访问格式；不代表服务器母版或受限画质',
                'selected': {k: selected.get(k) for k in fields},
                'available_formats': [{k: f.get(k) for k in fields} for f in formats]}
    write_json(folder / 'source.json', manifest)
    print(f'已下载: {media}', flush=True)
    return media


def search(query):
    folder = job_dir('video', 'search')
    result = json.loads(run(ytdlp_base() + ['--flat-playlist', '--dump-single-json',
                                           f'ytsearch10:{query}'], folder / 'search.log'))
    entries = []
    for e in result.get('entries', []):
        entries.append({'title': e.get('title'), 'url': e.get('url'),
                        'channel': e.get('channel'), 'channel_id': e.get('channel_id'),
                        'official_channel_verified': e.get('channel_id') in CONFIG['official_channels']})
    write_json(folder / 'search.json', entries)
    print(json.dumps(entries, ensure_ascii=False, indent=2))
    return entries


def video_index(source, folder):
    info = json.loads(run([tool('ffprobe'), '-v', 'error', '-select_streams', 'v:0',
                           '-show_streams', '-show_format', '-of', 'json', source]))
    if not info.get('streams'):
        raise ValueError('视频没有画面流')
    stream = info['streams'][0]
    if stream.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('检测到 HDR；请明确色调映射策略，或选择公开视频中的 SDR 版本')
    if stream.get('sample_aspect_ratio') not in (None, 'N/A', '0:1', '1:1'):
        raise ValueError('非方形像素视频需先明确显示比例转换策略')
    print('读取实际帧时间戳（不按名义 FPS 猜测）…', flush=True)
    data = json.loads(run([tool('ffprobe'), '-v', 'error', '-select_streams', 'v:0',
                           '-show_frames', '-show_entries',
                           'frame=best_effort_timestamp_time,pts_time,duration_time', '-of', 'json', source],
                          folder / 'ffprobe.log'))
    origin = float(stream.get('start_time') or 0)
    rows = []
    for n, f in enumerate(data.get('frames', [])):
        value = f.get('best_effort_timestamp_time', f.get('pts_time'))
        if value is None:
            raise ValueError('源视频含无时间戳帧；不能保证精准抽帧')
        rows.append({'index': n, 'pts': float(value), 'time': float(value) - origin,
                     'duration': float(f.get('duration_time') or 0)})
    if not rows or any(b['time'] < a['time'] for a, b in zip(rows, rows[1:])):
        raise ValueError('没有有效的单调帧时间戳')
    write_json(folder / 'video-info.json', {'stream': stream, 'format': info.get('format'),
                                           'timeline_origin': origin, 'frames': rows})
    return rows


def select_indices(rows, target, nearby, count=21, radius=1):
    times = [r['time'] for r in rows]
    end = times[-1] + (rows[-1]['duration'] or (times[-1] - times[-2] if len(times) > 1 else 0))
    if target < times[0] - 1e-6 or target >= end:
        raise ValueError(f'时间超出视频范围: {target:.6f}s; 范围 {times[0]:.6f}–{end:.6f}s')
    nearest = min(range(len(rows)), key=lambda i: (round(abs(times[i] - target), 9), times[i]))
    if not nearby:
        return [nearest]
    eligible = [i for i, t in enumerate(times) if target - radius <= t <= target + radius]
    if not eligible:
        return [nearest]
    positions = np.linspace(times[eligible[0]], times[eligible[-1]], min(count, len(eligible)))
    chosen = {min(eligible, key=lambda i: abs(times[i] - float(t))) for t in positions}
    chosen.add(nearest)
    return sorted(chosen)


@lru_cache(maxsize=1)
def anime_detector():
    model = ROOT / 'models/lbpcascade_animeface.xml'
    if not model.is_file():
        return None
    # OpenCV's Windows filename loader cannot reliably open Unicode paths.
    storage = cv2.FileStorage(model.read_text(encoding='utf-8'), cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    detector = cv2.CascadeClassifier()
    detector.read(storage.getFirstTopLevelNode())
    storage.release()
    if detector.empty():
        raise RuntimeError('动漫脸定位模型无法加载')
    return detector


def frame_metrics(path, roi=None):
    with Image.open(path) as im:
        im.thumbnail((960, 960))
        rgb = np.array(im.convert('RGB'))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    face_boxes = []
    detector = anime_detector()
    if detector is not None:
        face_boxes = np.asarray(detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24))).tolist()
    if roi is not None:
        x, y, rw, rh = roi
        crop = gray[int(y*h):max(int((y+rh)*h), int(y*h)+1), int(x*w):max(int((x+rw)*w), int(x*w)+1)]
    elif face_boxes:
        x, y, fw, fh = max(face_boxes, key=lambda b: b[2] * b[3])
        crop = gray[y:y+fh, x:x+fw]
    else:
        crop = gray[h//6:5*h//6, w//6:5*w//6]
    smooth = cv2.GaussianBlur(gray, (3, 3), 0.6)
    dx = np.abs(np.diff(gray.astype(float), axis=1))
    dy = np.abs(np.diff(gray.astype(float), axis=0))
    block = max(0., float(dx[:, 7::8].mean() - dx.mean())) if w > 16 else 0.
    block += max(0., float(dy[7::8, :].mean() - dy.mean())) if h > 16 else 0.
    hist = cv2.calcHist([cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)], [0, 1], None, [24, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    metrics = {'sharpness': float(cv2.Laplacian(smooth, cv2.CV_64F).var()),
               'subject_sharpness': float(cv2.Laplacian(cv2.GaussianBlur(crop, (3, 3), .6), cv2.CV_64F).var()),
               'blockiness_proxy': block, 'face_count': len(face_boxes),
               'dark_or_white_fraction': float(np.mean((gray < 5) | (gray > 250))),
               'face_boxes_on_thumbnail': face_boxes,
               'eye_state': 'requires_visual_review', 'subtitle_occlusion': 'requires_visual_review',
               'expression_and_deformation': 'requires_visual_review'}
    return metrics, hist, cv2.resize(gray, (160, 90))


def contact_sheet(records, folder, name):
    cols = min(3, len(records))
    canvas = Image.new('RGB', (cols * 480, math.ceil(len(records) / cols) * 310), '#17191f')
    draw = ImageDraw.Draw(canvas)
    for i, r in enumerate(records):
        x, y = (i % cols) * 480, (i // cols) * 310
        with Image.open(r['path']) as im:
            im.thumbnail((470, 270))
            canvas.paste(im, (x + (480-im.width)//2, y + 5 + (270-im.height)//2))
        draw.text((x+10, y+279), f"#{r['rank']}  PTS={r['time']:.6f}s  score={r['score']:.3f}", fill='white')
    canvas.save(folder / name)


def extract(source, target, nearby=False, count=21, radius=1, roi=None, extract_only=False,
            level='faithful', scale=None, gpu=None):
    source = Path(source).resolve(strict=True)
    folder = job_dir('frames', f'{source.stem}_{target:.3f}s')
    source_hash = digest(source)
    rows = video_index(source, folder)
    chosen = select_indices(rows, target, nearby, count, radius)
    # Decode original video stream and select decoded frame numbers. No fps filter, seek guess, screenshot or re-encoding.
    expr = '+'.join(f'eq(n\\,{i})' for i in chosen)
    print(f'从视频原始分辨率提取 {len(chosen)} 帧…', flush=True)
    run([tool('ffmpeg'), '-hide_banner', '-v', 'error', '-n', '-i', source,
         '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', f'select={expr}',
         '-fps_mode', 'passthrough', '-frames:v', str(len(chosen)),
         '-pix_fmt', 'rgb24', folder / 'candidate_%03d.png'], folder / 'extract.log')
    files = sorted(folder.glob('candidate_*.png'))
    if len(files) != len(chosen):
        raise RuntimeError('抽帧数量与时间戳索引不符')
    records, hists, thumbs = [], [], []
    for p, i in zip(files, chosen):
        metrics, hist, thumb = frame_metrics(p, roi)
        records.append({**rows[i], 'path': str(p), 'sha256': digest(p), **metrics})
        hists.append(hist)
        thumbs.append(thumb)
    center = min(range(len(records)), key=lambda i: abs(records[i]['time']-target))
    # Only compare within the shot contiguous with the requested moment.
    left = right = center
    while left > 0 and cv2.compareHist(hists[left], hists[left-1], cv2.HISTCMP_BHATTACHARYYA) < .48:
        left -= 1
    while right < len(records)-1 and cv2.compareHist(hists[right], hists[right+1], cv2.HISTCMP_BHATTACHARYYA) < .48:
        right += 1
    def norm(key):
        vals = np.log1p([r[key] for r in records])
        spread = float(np.ptp(vals))
        return (vals - vals.min()) / spread if spread > 1e-8 else np.full(len(vals), .5)
    sharp, subject, block = norm('sharpness'), norm('subject_sharpness'), norm('blockiness_proxy')
    for i, r in enumerate(records):
        dist = cv2.compareHist(hists[center], hists[i], cv2.HISTCMP_BHATTACHARYYA)
        r['composition_distance_proxy'] = float(dist)
        r['same_shot_proxy'] = left <= i <= right
        r['score'] = float(.35*sharp[i] + .40*subject[i] - .10*block[i]
                           - .10*abs(r['time']-target)/max(radius, .01) - .18*dist
                           - .25*r['dark_or_white_fraction'] - (0 if r['same_shot_proxy'] else 1))
    ranked = sorted(records, key=lambda r: (-r['score'], abs(r['time']-target)))
    for rank, r in enumerate(ranked, 1):
        r['rank'] = rank
    # Preserve three distinct candidates when available; all originals also remain.
    top = ranked[:3]
    for r in top:
        shutil.copy2(r['path'], folder / f"top{r['rank']}_{r['time']:.6f}s.png")
    selected = ranked[0]
    shutil.copy2(selected['path'], folder / 'selected_original.png')
    contact_sheet(ranked, folder, 'candidates_contact_sheet.jpg')
    contact_sheet(top, folder, 'top3_contact_sheet.jpg')
    manifest = {'source': str(source), 'source_sha256': source_hash, 'requested_time': target,
                'mode': 'nearby' if nearby else 'exact', 'radius_seconds': radius if nearby else 0,
                'timestamp_policy': 'nearest actual display PTS; tie -> earlier frame',
                'selected': selected, 'time_error_seconds': selected['time']-target,
                'ranking_method': 'heuristic: face/ROI sharpness, sharpness, blockiness, shot and time proximity',
                'visual_review': 'pending' if nearby else 'not_requested',
                'semantic_limitations': ['闭眼', '面部自然度', '字幕遮挡', '转场残影或拉伸须视觉复核'],
                'candidates': ranked, 'original': str(folder / 'selected_original.png')}
    if digest(source) != source_hash:
        raise RuntimeError('源视频哈希发生变化')
    write_json(folder / 'frames.json', manifest)
    print(f'原帧与候选: {folder}\n选择 {selected["time"]:.6f}s，偏差 {selected["time"]-target:+.6f}s', flush=True)
    if not extract_only:
        manifest['enhancement'] = enhance(folder / 'selected_original.png', level, scale, gpu)
        write_json(folder / 'frames.json', manifest)
    return manifest


def choose(manifest_path, rank, reason, level, scale, gpu):
    path = Path(manifest_path).resolve(strict=True)
    data = json.loads(path.read_text(encoding='utf-8'))
    row = next((r for r in data['candidates'] if r['rank'] == rank), None)
    if row is None:
        raise ValueError('候选序号不存在')
    src = Path(row['path'])
    if digest(src) != row['sha256']:
        raise RuntimeError('候选原帧已变更')
    # A review gets its own immutable record; previous automatic result remains.
    folder = job_dir('frames', 'reviewed_selection')
    raw = folder / 'selected_original.png'
    shutil.copy2(src, raw)
    result = enhance(raw, level, scale, gpu)
    write_json(folder / 'review.json', {'previous_manifest': str(path), 'selected': row,
                                      'visual_review': 'completed', 'reason': reason,
                                      'enhancement': result})
    return result


def main():
    p = argparse.ArgumentParser(description='二次元图片 / 视频帧获取与画质修复（默认保真 2×）')
    sub = p.add_subparsers(dest='cmd', required=True)
    def quality(parser):
        parser.add_argument('--level', choices=list(LEVELS), default='faithful')
        parser.add_argument('--scale', type=int, choices=(2, 4))
        parser.add_argument('--gpu', type=int)
    img = sub.add_parser('image', help='图片增强；支持多个路径')
    img.add_argument('paths', nargs='+')
    quality(img)
    vid = sub.add_parser('video', help='公开视频 URL 或本地视频 → 原始帧 → 增强')
    vid.add_argument('source')
    vid.add_argument('--time', required=True, type=seconds)
    vid.add_argument('--nearby', action='store_true', help='前后 1 秒最佳帧搜索')
    vid.add_argument('--radius', type=float, default=1.)
    vid.add_argument('--candidates', type=int, default=21)
    vid.add_argument('--roi', type=float, nargs=4, metavar=('X', 'Y', 'W', 'H'), help='主体归一化区域')
    vid.add_argument('--extract-only', action='store_true', help='候选先供视觉复核，再用 choose 增强')
    quality(vid)
    dl = sub.add_parser('download', help='下载最高公开可访问画质（原编码、仅视频流）')
    dl.add_argument('url')
    se = sub.add_parser('search', help='搜索并标记已核实官方频道，保存候选来源')
    se.add_argument('query')
    ch = sub.add_parser('choose', help='视觉复核后选用某个候选并增强')
    ch.add_argument('manifest')
    ch.add_argument('--rank', required=True, type=int)
    ch.add_argument('--reason', required=True)
    quality(ch)
    sub.add_parser('doctor', help='检查工具、模型和依赖')
    args = p.parse_args()
    if args.cmd == 'image':
        for source in args.paths:
            enhance(source, args.level, args.scale, args.gpu)
    elif args.cmd == 'video':
        if not math.isfinite(args.radius) or not 0 < args.radius <= 10 or not 3 <= args.candidates <= 121:
            p.error('radius 范围 (0,10]；candidates 范围 [3,121]')
        if args.roi:
            x, y, w, h = args.roi
            if not all(math.isfinite(v) for v in args.roi) or min(x,y) < 0 or min(w,h) <= 0 or x+w > 1 or y+h > 1:
                p.error('ROI 必须位于 [0,1] 图像范围内')
        src = download(args.source) if re.match(r'^https?://', args.source) else args.source
        extract(src, args.time, args.nearby, args.candidates, args.radius, args.roi,
                args.extract_only, args.level, args.scale, args.gpu)
    elif args.cmd == 'download':
        download(args.url)
    elif args.cmd == 'search':
        search(args.query)
    elif args.cmd == 'choose':
        choose(args.manifest, args.rank, args.reason, args.level, args.scale, args.gpu)
    elif args.cmd == 'doctor':
        print('Python:', sys.executable)
        for name in ('ffmpeg', 'ffprobe', 'realesrgan'):
            print(name, tool(name))
        for ext in ('bin', 'param'):
            path = ROOT / f'models/realesrgan-x4plus-anime.{ext}'
            print(path, digest(path))
        print(run([sys.executable, '-m', 'yt_dlp', '--version']))
        print('GPU:', CONFIG['gpu_id'] if CONFIG['gpu_id'] is not None else 'auto', '（GPU 实际运行请查看 inference.log）')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print(f'错误: {e}', file=sys.stderr)
        sys.exit(1)
