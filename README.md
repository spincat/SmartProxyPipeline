# SmartProxyPipeline

## 简介

`SmartProxyPipeline` 是一个自动化代理订阅处理工具，支持模板化、验证、去重、整合和上传功能。用于从多个订阅源下载代理地址，验证这些地址的有效性，并将有效的地址上传到 Git 仓库。该工具支持两种运行模式：`local` 和 `github-action`，适用于需要定期更新代理地址的场景。

## 功能

- **订阅源下载**：从配置的订阅源 URL 模板生成多个订阅 URL，并发下载订阅内容。
- **地址验证**：使用 `ping` 命令验证下载的代理地址的有效性。
- **Git 上传**：将有效的代理地址保存到文件，并上传到指定的 Git 仓库。
- **多线程处理**：使用多线程并发下载和验证地址，提高处理效率。

## 配置文件 (`config.json`)

配置文件定义了程序的运行参数，以下是配置文件的详细说明：

- **`mode`**: 运行模式，可以是 `github-action` 或 `local`。
- **`download`**: 配置下载订阅源的参数。
  - `providers`: 订阅源的 URL 模板。
  - `retain_days`: 回溯的天数，用于生成订阅 URL。
  - `output_file`: 下载的地址保存的文件名。
- **`validation`**: 配置验证地址有效性的参数。
  - `ping_timeout`: Ping 操作的超时时间。
  - `valid_output_file`: 有效地址保存的文件名。
  - `validation_interval`: 验证间隔时间。
- **`proxies`**: 配置代理设置。
  - `enable_proxy`: 是否启用代理。
  - `http` 和 `https`: 代理地址。
- **`git`**: 配置 Git 上传参数。
  - `enable_git_upload`: 是否启用 Git 上传。
  - `repo_url`: Git 仓库的 URL。
  - `repo_path`: 本地 Git 仓库的路径。
  - `username` 和 `password`: Git 用户名和密码（或 token）。
  - `user_name` 和 `user_email`: Git 用户身份信息。

## 使用说明

### 1. 本地运行

1. **克隆仓库**：
   ```bash
   git clone https://github.com/your-repo/v2rayN-updater.git
   cd v2rayN-updater
   ```
2. **安装依赖**：
   在项目根目录下运行以下命令安装所有依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**：
   在本地运行前，确保设置了以下环境变量：
   - `GIT_USERNAME`: Git 用户名。
   - `GIT_PASSWORD`: Git 密码或 token。

4. **运行程序**：
   ```bash
   python v2rayN_updater.py
   ```

### 2. GitHub Actions 运行

1. **Fork 仓库**：
   将仓库 Fork 到你的 GitHub 账户。

2. **配置 Secrets**：
   在 GitHub 仓库的 `Settings -> Secrets` 中配置以下 Secrets：
   - `GIT_USERNAME`: Git 用户名。
   - `GIT_PASSWORD`: Git 密码或 token。

3. **触发 Actions**：
   程序会自动根据workflow 配置文件的 `schedule` 定期运行，或者你可以手动触发 GitHub Actions。

## 注意事项

1. **GitHub Actions 配置**：
   - 在使用 GitHub Actions 时，需要先配置 GitHub Actions 的权限：
     - 进入项目：`Settings > Secrets and variables > Actions > Repository secrets`，设置好环境变量（`GIT_USERNAME`、`GIT_PASSWORD`）。
   - 确保 GitHub Actions 具有推送权限：
     - 仓库设置：到 `Settings > Actions > General > Workflow permissions` 中，启用 `Read and write permissions`。

2. **本地运行**：
   - 在本地运行时，确保设置了以下环境变量：
     - `GIT_USERNAME`: Git 用户名。
     - `GIT_PASSWORD`: Git 密码或 token。

3. **日志**：
   - 程序使用 `logging` 模块记录运行时的信息、警告和错误，日志格式如下：
     ```
     2023-10-01 12:00:00,000 - INFO - Downloaded and combined 100 addresses.
     2023-10-01 12:00:05,000 - INFO - File written successfully: valid_addresses.txt
     ```

## 常见问题

1. **Git 上传失败**：
   - 确保 `config.json` 中的 `repo_url` 和 `repo_path` 配置正确。
   - 检查 GitHub Actions 的 `GIT_USERNAME` 和 `GIT_PASSWORD` 是否配置正确。
   - 确保 GitHub Actions 具有推送权限。

2. **代理地址验证失败**：
   - 检查 `ping_timeout` 配置是否合理，适当增加超时时间。
   - 确保代理地址格式正确，支持 `ss://`, `vmess://`, `trojan://`, `vless://` 等协议。


## 贡献

欢迎提交 Issue 和 Pull Request 来改进此项目。

## 许可证

本项目采用 MIT 许可证，详情请参阅 [LICENSE](LICENSE) 文件。

---

**注意**：请确保在使用此工具时遵守相关法律法规和服务条款。