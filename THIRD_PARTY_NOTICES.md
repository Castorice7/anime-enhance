# Third-party notices

The repository's MIT license covers its workflow, setup, launchers, documentation and original procedural test fixtures. It does not relicense upstream tools, neural-network weights, videos or illustrations.

| Component | Use | Upstream notice |
| --- | --- | --- |
| Real-ESRGAN | Anime super-resolution model/project | [BSD-3-Clause project license](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE) |
| Real-ESRGAN-ncnn-vulkan | External Vulkan inference executable | [MIT and inherited notice](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/blob/master/LICENSE) |
| lbpcascade_animeface | Face-location scoring, never reconstruction | [MIT notice embedded in XML](https://github.com/nagadomi/lbpcascade_animeface/blob/master/lbpcascade_animeface.xml) |
| Deno | JavaScript runtime for yt-dlp | [MIT](https://github.com/denoland/deno/blob/main/LICENSE.md) |
| yt-dlp | Public video search/download | [License and notices](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE) |
| FFmpeg / FFprobe | Video decoding and timestamps | [License depends on build](https://ffmpeg.org/legal.html) |

Programs and models are downloaded from upstream during installation and excluded from Git. The NCNN distribution has additional dependencies with their own notices. Before distributing a bundled binary package, review the exact distribution's complete notices and obligations.

The downloaded anime-face XML contains an MIT notice that must remain intact. Hashes identify tested bytes and do not grant rights. Selected license texts are retained in licenses/ for reference.

Python versions are listed in requirements-lock.txt; installed packages contain their individual license metadata and transitive notices.

Public tests generate original geometric fixtures and color frames. No character artwork, PV files, extracted game frames or user images are committed. Earlier local visual evaluations used external sample material, which is excluded from this source release.

Documentation links identify example public pages; public access alone is not permission to redistribute their content. Use media you own or are authorized to process and share.

HoYoverse, miHoYo, game titles and characters belong to their respective owners. This is an independent community tool, not an official product.
