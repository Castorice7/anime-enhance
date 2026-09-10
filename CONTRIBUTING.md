# Contributing

感谢参与。提交改动前，请确保：

1. 使用 Python 3.12，并在项目虚拟环境中运行测试。
2. 运行 `python -m unittest discover -s tests -p "test_*.py" -v`。
3. 如果改动涉及模型、FFmpeg 或视频时间戳，再运行 `tests/verify_workflow.py`。
4. 不提交用户图片、视频、抽帧、模型权重、二进制文件、日志、私有配置或密钥。
5. 不引入扩散模型、生成式补画、人脸/手部重建或绕过站点访问限制的代码。

提交问题时，请附 Windows 版本、Python 版本、`run.cmd doctor` 输出和可复现的命令；不要上传私人媒体或包含个人路径的日志。
