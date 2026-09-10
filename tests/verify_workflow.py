"""Integration checks: actual NCNN inference, alpha and lossless VFR frame identity."""
import contextlib
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workflow as wf


def main():
    folder = wf.job_dir('input', 'verification')
    report = {'checks': [], 'artifacts': [], 'fixture_folder': str(folder)}
    def passed(name):
        report['checks'].append(name)
        print('PASS:', name, flush=True)
    assert wf.anime_detector() is not None and not wf.anime_detector().empty()
    passed('Anime face locator loads successfully from Unicode workspace')
    # Original procedural fixture: no user files or third-party artwork required.
    sample = Image.new('RGB', (64, 64), '#acbcd8')
    draw = ImageDraw.Draw(sample)
    draw.polygon([(4, 59), (27, 3), (58, 53)], fill='#eed5a1', outline='#253242', width=2)
    draw.ellipse((22, 23, 39, 40), fill='#839acc', outline='#253242', width=2)
    draw.line([(6, 48), (31, 15), (56, 49)], fill='#50364a', width=1)
    sample.save(folder / 'fixture.jpg', quality=65)
    alpha = np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (64, 1))
    rgba = sample.copy()
    rgba.putalpha(Image.fromarray(alpha))
    rgba.save(folder / '透明 渐变.png')
    sample.save(folder / 'test.webp', lossless=True)
    palette = sample.quantize(colors=32)
    palette.save(folder / 'palette.png', transparency=0)
    for name, level, scale in [('透明 渐变.png', 'faithful', 2), ('透明 渐变.png', 'ultra', 4),
                               ('test.webp', 'clear', 2), ('palette.png', 'faithful', 2),
                               ('fixture.jpg', 'faithful', 2)]:
        src = folder / name
        before = wf.digest(src)
        with contextlib.redirect_stdout(io.StringIO()):
            result = wf.enhance(src, level, scale)
        dst = Image.open(result['output'])
        assert dst.size == (64 * scale, 64 * scale)
        assert before == wf.digest(src)
        orig = Image.open(src)
        if name not in ('test.webp', 'fixture.jpg'):
            expected = orig.convert('RGBA').getchannel('A').resize(dst.size, Image.Resampling.BILINEAR)
            assert dst.mode == 'RGBA'
            assert np.array_equal(np.array(dst.getchannel('A')), np.array(expected))
        passed(f'NCNN {name} {level} {scale}x: dimensions, original hash, alpha when present')
        report['artifacts'].append(result)
    assert report['artifacts'][0]['output'] != report['artifacts'][1]['output']
    passed('Repeated same input produces distinct output paths')
    try:
        wf.enhance(folder / '透明 渐变.png', 'ultra', 2)
        raise AssertionError('ultra 2x accepted')
    except ValueError:
        passed('Invalid ultra + 2x rejected')
    assert wf.seconds('01:32.417') == 92.417
    assert wf.seconds('1分32.417秒') == 92.417
    assert wf.select_indices([{'time': 92.4, 'duration': .034}, {'time': 92.434, 'duration': .033}], 92.417, False) == [0]
    passed('Fractional timestamps parsed without integer rounding')
    # Known unique pixel values; VFR timing and FFV1 lossless codec give independent ground truth.
    colors = [(22, 51, 90), (50, 80, 110), (80, 100, 130), (120, 140, 160), (170, 180, 190)]
    for i, color in enumerate(colors):
        Image.new('RGB', (96, 64), color).save(folder / f'vfr{i}.png')
    durations = [.04, .12, .20, .08, .24]
    lines = ['ffconcat version 1.0']
    for i, d in enumerate(durations):
        lines += [f"file 'vfr{i}.png'", f'duration {d}']
    lines += ["file 'vfr4.png'"]
    (folder / 'vfr.ffconcat').write_text('\n'.join(lines), encoding='ascii')
    video = folder / 'vfr.mkv'
    wf.run([wf.tool('ffmpeg'), '-hide_banner', '-v', 'error', '-n', '-f', 'concat', '-safe', '0',
            '-i', folder / 'vfr.ffconcat', '-fps_mode', 'vfr', '-c:v', 'ffv1', '-pix_fmt', 'bgr0', video])
    result = wf.extract(video, .30, extract_only=True)
    assert abs(result['selected']['time'] - .36) < 1e-6, result['selected']
    assert abs(result['time_error_seconds'] - .06) < 1e-6
    raw = np.array(Image.open(result['original']).convert('RGB'))
    assert np.all(raw == colors[3]), raw[0, 0]
    passed('VFR exact .300s selects actual .360s frame; pixels match independent lossless fixture')
    nearby = wf.extract(video, .36, nearby=True, radius=.30, extract_only=True)
    for row in nearby['candidates']:
        assert abs(row['time'] - .36) <= .30 + 1e-6
        expected_color = colors[min(row['index'], 4)]
        assert np.all(np.array(Image.open(row['path']).convert('RGB')) == expected_color)
    assert any(abs(row['time']-.36) < 1e-6 for row in nearby['candidates'])
    assert len(nearby['candidates']) >= 3
    passed('VFR nearby frames are inside window, include center and retain exact source pixels')
    rows = [{'time': .0, 'duration': .04}, {'time': .04, 'duration': .12}, {'time': .16, 'duration': .2}]
    try:
        wf.select_indices(rows, .5, False)
        raise AssertionError('out-of-range accepted')
    except ValueError:
        passed('Out-of-range timestamp rejected')
    report['passed'] = True
    wf.write_json(wf.ROOT / 'tests/latest-results.json', report)
    print(f"All {len(report['checks'])} integration checks passed.")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
