# Release validation — 2026-09-10

## Scope

The staged source was exported with `git archive` into a new directory. The exported tree contained only source files, documentation, license notices and empty runtime-directory placeholders. No existing virtual environment, downloaded tool, model, input image, private configuration or result file was copied.

`setup.py` then downloaded the pinned upstream assets and Python dependencies, verified asset hashes and created a new virtual environment with user-site packages disabled. This tests a fresh source installation on the same Windows host; it is not a fresh operating-system image or a claim of compatibility with every GPU.

Host: Windows x64, Python 3.12, NVIDIA GeForce RTX 4070 Laptop GPU, FFmpeg/FFprobe 8.1.2 already on PATH. The exported default configuration used NCNN GPU auto-selection. No system Python packages were changed.

## Results

| Check | Result |
| --- | --- |
| Fresh installation from source-only export | Passed; 45.6 seconds on the test connection |
| `pip check` | Passed |
| `run.cmd doctor` from the exported project | Passed |
| CPU regression suite | 10 tests passed |
| Real Vulkan/NCNN/FFmpeg integration suite | 12 checks passed; 27.7 seconds |
| CLI nearby frame extraction → default 2× enhancement | Passed; 96×64 synthetic video frame → 192×128 PNG |
| Public official video metadata/formats probe | Passed; official Robin PV exposed up to 3840×1632 |
| Source-only payload audit | Passed; no runtime media, executables, model weights, private workspace paths or common token/private-key patterns |

The GPU checks cover transparent-gradient PNG at 2× and 4×, palette transparency, WebP, JPEG, source hashes, independent output paths, invalid scale combinations, fractional timestamps and out-of-range timestamps. The VFR fixture uses lossless FFV1 and known pixel values: requesting 0.300 s selects the actual 0.360 s frame, whose pixels match the independently generated original.

The CPU suite also checks equal-distance timestamps despite floating-point rounding, nearby-window bounds, 16-bit input rejection and large-image rejection before inference.

Public test fixtures are original procedural geometry and color frames. They test pipeline integrity, not visual fidelity on every anime character. Before release preparation, a local end-to-end visual evaluation also processed an official 3840×1632 PV frame into 7680×3264 with the same anime model; the third-party video, frame and previews are intentionally excluded from this repository.

## Reproduce

```powershell
py -3.12 setup.py
.\tools\venv\Scripts\python.exe -m pip check
.\run.cmd doctor
.\tools\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\tools\venv\Scripts\python.exe tests\verify_workflow.py
```

GitHub Actions runs the CPU suite. Actual GPU integration is a separate local check; an Actions success alone is not evidence of Vulkan inference. Online access and available formats can change. Semantic best-frame judgments still require visual review, as documented in README.md.
