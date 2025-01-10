# SmartProxyPipeline

一个自动化代理订阅处理工具，支持模板化、验证、去重、整合和上传功能。

## 功能
- 自动下载代理订阅文件
- 验证代理地址的有效性
- 去重并整合代理地址
- 支持上传整合后的代理列表

## 安装
1. 克隆仓库：
   ```bash
   git clone https://github.com/spincat/SmartProxyPipeline.git

2. 安装依赖：
   ```bash
   pip install -r requirements.txt

## 使用
1. 配置 config.json 文件。

2. 运行主程序：
   ```bash
   python main.py


## 注意
1. 在使用Github Action时，需要先配置Github Action 的权限：
   进入项目：Settings > Secrets and variables > Actions > Repository secrets 设置好环境变量（GIT_USERNAME、GIT_PASSWORD）

2. 并确保 GitHub Actions 具有推送权限：
   仓库设置：到 Settings > Actions > General > Workflow permissions 中，启用 Read and write permissions。

## 贡献
欢迎提交 Issue 和 Pull Request！

## 许可证
本项目采用 MIT License。
