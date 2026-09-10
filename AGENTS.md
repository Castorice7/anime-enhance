# anime-enhance agent workflow

Read README.md first. Use tools/venv/Scripts/python.exe; do not install into system Python.

- Default image requests to faithful 2x. Only explicit 4x or ultra requests produce 4x outputs.
- Use this workflow, not imagegen, diffusion, inpainting, face restoration or body/hand reconstruction.
- Preserve original images, videos, extracted frames and previous outputs. Do not promise identical details from learned super-resolution.
- Prefer supplied URLs. For titles or character/PV names, search public official sources and verify publisher, language and version. A title containing "official" is insufficient evidence.
- Download the highest normally accessible format. Do not bypass DRM, payment, authentication or access restrictions; do not silently use reposts.
- Exact timestamps: `video SOURCE --time TIME`. Report actual PTS and error when material.
- Nearby requests: `video SOURCE --time TIME --nearby --extract-only`. Inspect the contact sheet and full candidate PNGs as needed for open eyes, natural expression, blur, artifacts, composition, subtitles and transitions. Numeric scores alone cannot prove semantic quality.
- Choose the best without unnecessary confirmation: `choose MANIFEST --rank N --reason REASON`. Keep three candidates available when useful. Do not reconstruct open eyes if the requested shot has closed eyes.
- CLI image/download/extraction is independent; natural-language interpretation and semantic visual review require an assistant or person. Explain this boundary.
- Verify actual output and result.json before delivery. Run relevant tests for changes. Never commit runtime data, private paths, logs, credentials, third-party artwork or downloaded binaries.
