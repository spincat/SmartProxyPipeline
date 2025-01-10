import os
import json
import re
import base64
import requests
from datetime import datetime, timedelta
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import schedule
import jsonschema
import locale
from urllib.parse import unquote, urlparse, parse_qs, urlencode
from git import Repo

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置文件 Schema
# 配置文件 Schema
CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "download": {
            "type": "object",
            "properties": {
                "providers": {"type": "array"},
                "retain_days": {"type": "number"},
                "output_file": {"type": "string"}
            },
            "required": ["providers", "retain_days", "output_file"]
        },
        "validation": {
            "type": "object",
            "properties": {
                "ping_timeout": {"type": "number"},
                "valid_output_file": {"type": "string"},
                "validation_interval": {"type": "number"}
            },
            "required": ["ping_timeout", "valid_output_file", "validation_interval"]
        },
        "proxies": {
            "type": "object",
            "properties": {
                "http": {"type": "string"},
                "https": {"type": "string"}
            },
            "required": ["http", "https"]
        },
        "git": {
            "type": "object",
            "properties": {
                "enable_git_upload": {"type": "boolean"},
                "repo_url": {"type": "string"},
                "repo_path": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "user_name": {"type": "string"}, 
                "user_email": {"type": "string"} 
            },
            "required": ["enable_git_upload", "repo_url", "repo_path", "username", "password", "user_name", "user_email"]
        }
    },
    "required": ["download", "validation", "proxies", "git"]
}

def load_config():
    """
    加载并验证配置文件。

    Returns:
        dict: 配置文件的字典形式。

    Raises:
        jsonschema.ValidationError: 如果配置文件不符合预期的 schema。
        FileNotFoundError: 如果配置文件不存在。
    """
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)
        return config

def download_subscription(url, config):
    """
    下载订阅内容。

    Args:
        url (str): 订阅链接。

    Returns:
        str: 下载的内容，如果失败则返回 None。
    """
    try:
        # 从配置中获取代理设置
        proxies_config = config.get('proxies', {})
        enable_proxy = proxies_config.get('enable_proxy', False)
        
        # 如果启用代理，则设置代理
        proxies = None
        if enable_proxy and config.get('mode') == 'local':  # 仅在本机模式启用代理
            proxies = {
                'http': proxies_config.get('http'),
                'https': proxies_config.get('https')
            }
        
        # 添加常见的浏览器 User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, proxies=proxies, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            logging.warning(f"Access forbidden for {url}: {e}")
        else:
            logging.error(f"Failed to download {url}: {e}")
        return None
    except requests.RequestException as e:
        logging.error(f"Failed to download {url}: {e}")
        return None

def is_base64(content):
    """判断内容是否是 Base64 编码。"""
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
    return bool(base64_pattern.match(content))

def decode_base64(content):
    """解码 Base64 内容，如果是明码则直接返回。"""
    if is_base64(content):
        try:
            decoded_bytes = base64.b64decode(content)
            try:
                return decoded_bytes.decode('utf-8')
            except UnicodeDecodeError:
                return decoded_bytes.decode('latin-1')
        except Exception as e:
            logging.error(f"Failed to decode Base64 content: {e}")
            return content  # 如果解码失败，返回原始内容
    else:
        return content  # 如果是明码，直接返回

def is_valid_protocol(content):
    """
    检查内容是否包含常见协议前缀。

    Args:
        content (str): 待检查的内容。

    Returns:
        bool: 如果包含有效协议前缀则返回 True，否则返回 False。
    """
    return any(proto in content for proto in ['ss://', 'vmess://', 'trojan://', 'vless://'])

def generate_subscription_urls(base_url, days_back):
    """
    生成订阅 URL 列表。

    Args:
        base_url (str): 基础 URL 模板。
        days_back (int): 回溯的天数。

    Returns:
        list: 生成的订阅 URL 列表。
    """
    urls = []
    current_date = datetime.now()
    for days in range(days_back):
        date = current_date - timedelta(days=days)
        
        # 替换日期格式变量
        formatted_url = base_url
        formatted_url = formatted_url.replace('YYYY', date.strftime('%Y'))  # 替换年份
        formatted_url = formatted_url.replace('MM', date.strftime('%m'))    # 替换月份
        formatted_url = formatted_url.replace('DD', date.strftime('%d'))    # 替换日期

        # 处理 {0-4} 这样的范围
        match = re.search(r'\{(\d+)-(\d+)\}', formatted_url)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            for i in range(start, end + 1):
                urls.append(formatted_url.replace(match.group(0), str(i)))
        else:
            urls.append(formatted_url)
    return urls

def extract_host_port_from_line(line):
    """
    从地址行中提取主机地址和端口。

    Args:
        line (str): 地址行。

    Returns:
        str: 提取的主机地址和端口，格式为 "host:port"，如果失败则返回 None。
    """
    if line.startswith('vmess://'):
        try:
            decoded = base64.b64decode(line[8:]).decode('utf-8')
            config = json.loads(decoded)
            host = config.get('add', '')
            port = config.get('port', '')
            return f"{host}:{port}"
        except Exception as e:
            logging.error(f"Failed to parse vmess address {line}: {e}")
    elif line.startswith('ss://'):
        try:
            base64_part = line[len('ss://'):].split('#')[0]
            if '@' in base64_part:
                base64_part, host_port_part = base64_part.split('@', 1)
            else:
                host_port_part = base64_part
                base64_part = None

            if base64_part:
                base64_part = fix_base64_padding(base64_part)
                decoded = base64.b64decode(base64_part).decode('utf-8')
                if '@' in decoded:
                    host_port = decoded.split('@')[1].split(':')
                    if len(host_port) == 2:
                        return f"{host_port[0]}:{host_port[1]}"
                else:
                    host_port = host_port_part.split(':')
                    if len(host_port) == 2:
                        return f"{host_port[0]}:{host_port[1]}"
            else:
                host_port = host_port_part.split(':')
                if len(host_port) == 2:
                    return f"{host_port[0]}:{host_port[1]}"
        except Exception as e:
            logging.error(f"Failed to parse ss address {line}: {e}")
    elif line.startswith('trojan://'):
        try:
            after_prefix = line[len('trojan://'):]
            at_index = after_prefix.find('@')
            if at_index == -1:
                logging.error(f"No @ found in trojan address: {line}")
                return None
            host_port_part = after_prefix[at_index + 1:].split('?')[0].split('#')[0]
            host_port = host_port_part.split(':')
            if len(host_port) == 2:
                return f"{host_port[0]}:{host_port[1]}"
        except Exception as e:
            logging.error(f"Failed to parse trojan address {line}: {e}")
    elif line.startswith('vless://'):
        try:
            after_prefix = line[len('vless://'):]
            at_index = after_prefix.find('@')
            if at_index == -1:
                logging.error(f"No @ found in vless address: {line}")
                return None
            host_port_part = after_prefix[at_index + 1:].split('?')[0].split('#')[0]
            host_port = host_port_part.split(':')
            if len(host_port) == 2:
                return f"{host_port[0]}:{host_port[1]}"
        except Exception as e:
            logging.error(f"Failed to parse vless address {line}: {e}")
    logging.debug(f"No valid protocol found in address: {line}")
    return None

def fix_base64_padding(base64_str):
    """修复 Base64 字符串的填充字符。"""
    padding = len(base64_str) % 4
    if padding:
        base64_str += '=' * (4 - padding)
    return base64_str

def download_and_combine_subscriptions(config):
    """
    下载并整合订阅内容。

    Args:
        config (dict): 配置文件字典。
    """
    all_addresses = set()
    for provider in config['download']['providers']:
        base_url = provider['base_url']
        urls = generate_subscription_urls(base_url, config['download']['retain_days'])
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(download_subscription, url, config) for url in urls]
            for future in as_completed(futures):
                content = future.result()
                if content:
                    decoded_content = decode_base64(content)
                    if is_valid_protocol(decoded_content):
                        valid_lines = [line for line in decoded_content.splitlines() if is_valid_protocol(line)]
                        for line in valid_lines:
                            all_addresses.add(line)  # 直接存储原始地址
    with open(config['download']['output_file'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_addresses))
    logging.info(f"Downloaded and combined {len(all_addresses)} addresses.")

def ping_address(address, config):
    """
    Ping 地址并返回是否有效及延迟。

    Args:
        address (str): 地址。
        config (dict): 配置文件字典。

    Returns:
        tuple: (是否有效, 延迟时间)。
    """
    host_port = extract_host_port_from_line(address)
    if not host_port:
        logging.debug(f"Skipping address {address}: no host and port extracted")
        return False, float('inf')
    
    try:
        if os.name == 'nt':  # Windows
            param = '-n'
            timeout_param = '-w'
            timeout_value = config['validation']['ping_timeout']  # 单位为毫秒
            ping_command = ['ping', param, '1', timeout_param, str(timeout_value), host_port.split(':')[0]]
        else:  # Linux/Mac
            param = '-c'
            timeout_param = '-W'
            timeout_value = config['validation']['ping_timeout'] / 1000  # 转换为秒
            ping_command = ['ping', param, '1', timeout_param, str(timeout_value), host_port.split(':')[0]]
        
        logging.debug(f"Running ping command: {' '.join(ping_command)}")
        result = subprocess.run(ping_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 使用系统默认编码解码输出
        output = result.stdout.decode(locale.getpreferredencoding(), errors='ignore')
        logging.debug(f"Ping output for {host_port}: {output}")
        
        # 检查是否超时
        if "超时" in output or "timed out" in output or "timeout" in output:
            logging.debug(f"Ping failed for {host_port}: request timed out")
            return False, float('inf')
        
        # 提取延迟时间（通用模式）
        match = re.search(r'(\d+\.?\d*)\s*ms', output)
        if match:
            delay = float(match.group(1))  # 提取延迟时间
            logging.debug(f"Ping successful for {host_port}: delay={delay}ms")
            return True, delay
        
        logging.debug(f"Ping failed for {host_port}: no delay found in output")
        return False, float('inf')
    except Exception as e:
        logging.error(f"Failed to ping {host_port}: {e}")
        return False, float('inf')

def validate_addresses(config):
    """
    验证地址有效性，并在 ping 阶段去重。

    Args:
        config (dict): 配置文件字典。
    """
    with open(config['download']['output_file'], 'r', encoding='utf-8') as f:
        addresses = f.read().splitlines()
    
    valid_addresses = []  # 存储有效的地址
    tested_host_ports = set()  # 存储已测试的主机和端口组合
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(ping_address, address, config): address for address in addresses}
        for future in as_completed(futures):
            address = futures[future]
            host_port = extract_host_port_from_line(address)
            if not host_port:
                logging.debug(f"Skipping address {address}: no host and port extracted")
                continue
            
            # 如果主机和端口已测试过，跳过
            if host_port in tested_host_ports:
                logging.debug(f"Skipping duplicate host:port {host_port} for address {address}")
                continue
            
            # 标记主机和端口为已测试
            tested_host_ports.add(host_port)
            
            # 检查地址是否有效
            is_valid, delay = future.result()
            if is_valid:
                valid_addresses.append((address, delay))
    
    # 按延迟排序
    valid_addresses.sort(key=lambda x: x[1])
    output_file = config['validation']['valid_output_file']
    
    # 写入文件前，打印日志
    logging.info(f"准备写入文件: {output_file}")
    logging.info(f"有效地址数量: {len(valid_addresses)}")
    logging.info(f"输出文件路径: {os.path.abspath(output_file)}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join([addr for addr, _ in valid_addresses]))
        logging.info(f"文件写入成功: {output_file}")
    except Exception as e:
        logging.error(f"文件写入失败: {e}")

def upload_to_git(config):
    """
    将生成的 valid 文件上传到 Git 仓库。

    Args:
        config (dict): 配置文件字典。
    """
    # 检查是否启用 Git 上传
    if not config.get('git', {}).get('enable_git_upload', False):
        logging.info("Git upload is disabled in the config.")
        return  
    try:
        # 获取 valid 文件路径
        valid_file_path = config['validation']['valid_output_file']
        # 获取 Git 仓库路径
        repo_path = config.get('git', {}).get('repo_path', '.')
        # 获取 Git 仓库 URL
        repo_url = config.get('git', {}).get('repo_url')
        # 获取 Git 用户名和密码（或 token）
        git_username = os.getenv('GIT_USERNAME')
        git_password = os.getenv('GIT_PASSWORD')
        
        if not git_username or not git_password:
            logging.error("Git username or password is not provided in environment variables.")
            return
        else:
            logging.info(f"Git username: {git_username}")
            logging.info(f"Git password: [hidden]")  # 不要打印密码
        
        # 获取 Git 用户身份
        git_user_name = os.getenv('GIT_USERNAME')
        git_user_email = config.get('git', {}).get('user_email')
        
        if not repo_url:
            logging.error("Git repository URL is not provided in the config.")
            return
        
        # 检查 repo_path 是否存在
        if not os.path.exists(repo_path):
            logging.info(f"Directory {repo_path} does not exist. Creating it...")
            os.makedirs(repo_path)
        
        # 初始化或打开 Git 仓库
        try:
            repo = Repo(repo_path)
            logging.info(f"Using existing Git repository at {repo_path}.")
        except:
            logging.info(f"Initializing new Git repository at {repo_path}...")
            repo = Repo.init(repo_path)
            
            # 添加远程仓库
            if 'origin' not in repo.remotes:
                logging.info(f"Adding remote origin: {repo_url}")
                repo.create_remote('origin', repo_url)
            else:
                logging.info(f"Remote origin already exists: {repo.remotes.origin.url}")
        
        # 确保远程仓库 URL 正确
        origin = repo.remotes.origin
        if origin.url != repo_url:
            logging.info(f"Updating remote origin URL to {repo_url}...")
            origin.set_url(repo_url)
        
        # 切换到 main 分支
        if 'main' not in repo.heads:
            logging.info("Creating main branch...")
            repo.git.checkout('-b', 'main')
        else:
            logging.info("Switching to main branch...")
            repo.git.checkout('main')
        
        # 配置 Git 用户身份
        if git_user_name and git_user_email:
            logging.info("Configuring Git user identity...")
            repo.git.config('user.name', git_user_name)
            repo.git.config('user.email', git_user_email)
        else:
            logging.error("Git user identity (user_name and user_email) is not provided in the config.")
            return
        
        # 添加文件到 Git
        logging.info(f"Adding {valid_file_path} to Git...")
        repo.git.add(valid_file_path)
        
        # 提交更改
        logging.info("Committing changes...")
        repo.git.commit('-m', 'Update valid addresses')
        
        # 推送到远程仓库的 main 分支
        logging.info("Pushing changes to remote repository...")
        # 更新远程 URL，包含用户名和密码
        if git_username and git_password:
            origin_url = origin.url
            origin.set_url(f"https://{git_username}:{git_password}@github.com/{git_username}/SmartProxyPipeline.git")
        
        repo.git.push('origin', 'main')
        
        logging.info("Successfully uploaded valid addresses to Git repository.")
    except Exception as e:
        logging.error(f"Failed to upload to Git: {e}")

def main():
    """
    主程序入口。
    """
    try:
        config = load_config()
        download_and_combine_subscriptions(config)
        validate_addresses(config)

        # 两种模式都需上传到 Git（Git Action模式只能写入文件到临时目录）
        upload_to_git(config)
       
    except Exception as e:
        logging.error(f"An error occurred in the main loop: {e}")
    finally:
        logging.info("Cleaning up resources...")

if __name__ == "__main__":
  main()
