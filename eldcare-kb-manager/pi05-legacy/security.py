"""
安全模块：磁力链验证、文件扫描、病毒检测
"""
import re
import os
import hashlib
import subprocess
import logging

logger = logging.getLogger(__name__)

# 可接受的视频文件扩展名（白名单）
SAFE_VIDEO_EXTS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.ts', '.mts', '.m2ts', '.vob',
    '.srt', '.ass', '.ssa', '.sub'  # 字幕文件也算安全
}
# 危险扩展名（黑名单，直接拒绝）
DANGEROUS_EXTS = {
    '.exe', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jse',
    '.scr', '.pif', '.msi', '.dll', '.com', '.jar', '.sh',
    '.php', '.asp', '.aspx', '.cgi', '.py', '.rb', '.pl',
    '.zip', '.rar', '.7z', '.tar', '.gz',  # 压缩包可能有捆绑
}

# 危险关键词（检测标题/DN字段注入恶意文件名）
DANGEROUS_PATTERNS = [
    r'\.(exe|bat|cmd|ps1|vbs|js|jse|scr|pif|msi|dll|com)',  # 扩展名注入
    r'(virus|malware|trojan|ransomware|spyware|keylogger)',
    r'(hacked|pwned|crack|keygen|patch)',  # 伪装破解版
    r'^/|^[A-Z]:|~\||\\|\.\./',  # 路径遍历
    # 注意: 不再阻止 & 符号，因为电影标题常用 (如 "Foo & Bar")
]


def validate_magnet(magnet_uri: str) -> dict:
    """
    验证磁力链安全性，返回 {'safe': bool, 'reason': str, 'hash': str}
    """
    if not magnet_uri or not isinstance(magnet_uri, str):
        return {'safe': False, 'reason': '磁力链为空或类型错误', 'hash': ''}

    magnet_uri = magnet_uri.strip()
    if not magnet_uri.startswith('magnet:'):
        return {'safe': False, 'reason': '非磁力链格式', 'hash': ''}

    # 1. 检查是否包含危险 dn 字段（文件名注入）
    try:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(magnet_uri)
        params = parse_qs(parsed.query)

        dn = params.get('dn', [''])[0] if params.get('dn') else ''
        if dn:
            # 检查文件名是否包含危险扩展名注入
            dn_lower = dn.lower()
            for dangerous in DANGEROUS_EXTS:
                if dn_lower.endswith(dangerous):
                    return {'safe': False, 'reason': f'文件名注入危险扩展名: {dangerous}', 'hash': ''}

            # 检查危险关键词
            for pattern in DANGEROUS_PATTERNS:
                if re.search(pattern, dn, re.IGNORECASE):
                    return {'safe': False, 'reason': f'文件名含危险关键词: {pattern}', 'hash': ''}

    except Exception as e:
        return {'safe': False, 'reason': f'磁力链解析失败: {e}', 'hash': ''}

    # 2. 验证 btih hash 格式（40位十六进制）
    hash_match = re.search(r'urn:btih:([a-fA-F0-9]{40})', magnet_uri)
    if not hash_match:
        # 可能不是 BTIH 格式（也可能是 truncated hash），警告但不拒绝
        logger.warning(f'无法提取 BTIH hash: {magnet_uri[:80]}')
        btih_hash = ''
    else:
        btih_hash = hash_match.group(1).upper()

    # 3. 拒绝包含可执行文件扩展名的 tracker URL
    if re.search(r'&tr=.*\.(exe|bat|cmd|ps1|vbs|scr)', magnet_uri, re.IGNORECASE):
        return {'safe': False, 'reason': 'tracker URL 包含可疑可执行文件', 'hash': ''}

    # 4. 磁力链本身是安全的（只是字符串指针）
    return {'safe': True, 'reason': '磁力链格式验证通过', 'hash': btih_hash}


def validate_video_file(file_path: str) -> dict:
    """
    用 ffprobe 验证文件是否为真实视频文件（非 EXE 伪装）
    返回 {'safe': bool, 'reason': str, 'duration': int, 'format': str}
    """
    if not os.path.exists(file_path):
        return {'safe': False, 'reason': '文件不存在', 'duration': 0, 'format': ''}

    ext = os.path.splitext(file_path)[1].lower()

    # 先检查扩展名黑名单
    if ext in DANGEROUS_EXTS:
        return {'safe': False, 'reason': f'危险扩展名: {ext}', 'duration': 0, 'format': ''}

    # 用 ffprobe 探测实际文件类型
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            file_path
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {'safe': False, 'reason': 'ffprobe 无法解析文件（可能已损坏或非视频）', 'duration': 0, 'format': ''}

        import json
        info = json.loads(result.stdout)
        fmt = info.get('format', {})
        streams = info.get('streams', [])

        # 检查是否有视频流
        video_streams = [s for s in streams if s.get('codec_type') == 'video']
        if not video_streams:
            return {'safe': False, 'reason': '无视频流（可能是音频或假文件）', 'duration': 0, 'format': fmt.get('format_name', '')}

        duration = float(fmt.get('duration', 0) or 0)
        if duration < 60:
            return {'safe': False, 'reason': f'视频时长异常短: {duration:.0f}秒（可能是假冒文件）', 'duration': 0, 'format': fmt.get('format_name', '')}

        return {
            'safe': True,
            'reason': '视频文件验证通过',
            'duration': int(duration),
            'format': fmt.get('format_name', ''),
            'size': int(fmt.get('size', 0) or 0),
            'bitrate': int(fmt.get('bit_rate', 0) or 0),
        }

    except subprocess.TimeoutExpired:
        return {'safe': False, 'reason': 'ffprobe 超时', 'duration': 0, 'format': ''}
    except json.JSONDecodeError:
        return {'safe': False, 'reason': 'ffprobe 输出解析失败', 'duration': 0, 'format': ''}
    except Exception as e:
        return {'safe': False, 'reason': f'验证异常: {e}', 'duration': 0, 'format': ''}


def scan_file_with_clamav(file_path: str) -> dict:
    """
    用 ClamAV 扫描文件（需要安装 clamav-daemon）
    返回 {'clean': bool, 'threats': list}
    """
    import shutil
    clamav = shutil.which('clamscan') or shutil.which('clamdscan')
    if not clamav:
        return {'clean': None, 'threats': [], 'reason': 'ClamAV 未安装（sudo apt install clamav-daemon）'}

    try:
        result = subprocess.run(
            [clamav, '--no-summary', '--infected', file_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {'clean': True, 'threats': [], 'reason': '文件安全'}
        elif result.returncode == 1:
            # 有病毒
            lines = result.stdout.strip().split('\n')
            threats = [l for l in lines if l.strip()]
            return {'clean': False, 'threats': threats, 'reason': f'发现威胁: {len(threats)}个'}
        else:
            return {'clean': None, 'threats': [], 'reason': f'ClamAV 扫描失败 (code {result.returncode})'}
    except Exception as e:
        return {'clean': None, 'threats': [], 'reason': f'扫描异常: {e}'}


def install_clamav():
    """安装 ClamAV"""
    logger.info('正在安装 ClamAV...')
    result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'clamav-daemon'],
                          capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        logger.info('ClamAV 安装成功，运行 sudo systemctl start clamav-daemon 启动')
        return True
    else:
        logger.error(f'ClamAV 安装失败: {result.stderr}')
        return False


def compute_file_hash(file_path: str, algorithm='sha256') -> str:
    """计算文件 hash（用于信誉库查询）"""
    h = hashlib.new(algorithm)
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f'计算文件 hash 失败: {e}')
        return ''
