/**
 * Home Theater - Mobile Remote Control
 * 触摸手势、遥控面板、弹幕、字幕加载
 */

// 触摸滑动：左右滑动调节进度，上下滑动调节音量
(function() {
  let touchStartX = 0, touchStartY = 0, startVolume = 0, startTime = 0;

  document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('video-player');
    if (!video) return;

    video.addEventListener('touchstart', e => {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      startVolume = video.volume;
      startTime = video.currentTime;
    }, { passive: true });

    video.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].clientX - touchStartX;
      const dy = e.changedTouches[0].clientY - touchStartY;
      const absDx = Math.abs(dx);
      const absDy = Math.abs(dy);

      if (absDx > 30 && absDx > absDy * 1.5) {
        // 水平滑动：调节进度
        const seek = (dx > 0 ? 1 : -1) * Math.min(absDx * 0.5, 300);
        video.currentTime = Math.max(0, Math.min(video.duration, startTime + seek));
        showToast(`⏩ ${seek > 0 ? '+' : ''}${Math.round(seek)}s`);
      } else if (absDy > 30 && absDy > absDx * 1.5) {
        // 垂直滑动：调节音量
        const volDelta = -(dy / window.innerHeight) * 2;
        video.volume = Math.max(0, Math.min(1, startVolume + volDelta));
        showToast(`🔊 ${Math.round(video.volume * 100)}%`);
      }
    }, { passive: true });

    // 双击切换播放/暂停
    let lastTap = 0;
    video.addEventListener('touchend', e => {
      const now = Date.now();
      if (now - lastTap < 300) {
        video.paused ? video.play() : video.pause();
        showToast(video.paused ? '⏸ 已暂停' : '▶ 已播放');
      }
      lastTap = now;
    }, { passive: true });
  });
})();

// Toast 提示
function showToast(msg, duration = 1500) {
  const existing = document.getElementById('ht-toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.id = 'ht-toast';
  toast.style.cssText = `
    position: fixed; bottom: 100px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,0.85); color: #fff; padding: 10px 24px;
    border-radius: 24px; font-size: 0.9rem; z-index: 9999;
    pointer-events: none; white-space: nowrap;
    animation: ht-fadein 0.2s ease;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, duration);
}

// 字幕加载（VTT/SRT）
function loadSubtitle(url) {
  const video = document.getElementById('video-player');
  if (!url || !video) return;
  const track = video.addTextTrack('subtitles', '中文', 'zh');
  track.mode = 'showing';
  fetch(url).then(r => r.text()).then(text => {
    // 简单 SRT 解析
    const cues = parseSRT(text);
    cues.forEach(c => {
      try { track.addCue(new VTTCue(c.start, c.end, c.text)); } catch(e) {}
    });
  }).catch(() => {});
}

function parseSRT(text) {
  const cues = [];
  const blocks = text.trim().split(/\n\n+/);
  for (const block of blocks) {
    const lines = block.split('\n');
    if (lines.length < 3) continue;
    const timeMatch = lines[1].match(/(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/);
    if (!timeMatch) continue;
    const toSec = (h, m, s, ms) => +h*3600 + +m*60 + +s + +ms/1000;
    const start = toSec(timeMatch[1], timeMatch[2], timeMatch[3], timeMatch[4]);
    const end = toSec(timeMatch[5], timeMatch[6], timeMatch[7], timeMatch[8]);
    cues.push({ start, end, text: lines.slice(2).join('\n').replace(/<[^>]+>/g, '') });
  }
  return cues;
}

// 弹幕系统
const danmakuPool = [];
let danmakuEnabled = true;

function toggleDanmaku() {
  danmakuEnabled = !danmakuEnabled;
  showToast(danmakuEnabled ? '📺 弹幕开启' : '📺 弹幕关闭');
}

function sendDanmaku(text, color = '#ffffff') {
  if (!text) return;
  const video = document.getElementById('video-player');
  if (!video) return;
  const canvas = document.getElementById('danmaku-canvas') || createDanmakuCanvas();
  drawDanmaku(text, color, video.duration);
}

function createDanmakuCanvas() {
  const video = document.getElementById('video-player');
  const canvas = document.createElement('canvas');
  canvas.id = 'danmaku-canvas';
  canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10;';
  video.parentElement.style.position = 'relative';
  video.parentElement.appendChild(canvas);
  return canvas;
}

function drawDanmaku(text, color, currentTime) {
  const canvas = document.getElementById('danmaku-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  const x = canvas.width;
  const y = Math.random() * (canvas.height - 30) + 20;
  ctx.font = '20px "Noto Sans SC", sans-serif';
  const speed = 150; // px/s
  let opacity = 1;
  let bx = x;
  const duration = 8;

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    bx -= speed / 60;
    ctx.globalAlpha = opacity;
    ctx.fillStyle = color;
    ctx.fillText(text, bx, y);
    if (bx + ctx.measureText(text).width < 0) return;
    opacity = Math.max(0, opacity - 1/(duration*60));
    requestAnimationFrame(animate);
  }
  animate();
}

// 网络质量检测
function checkNetworkQuality() {
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (conn) {
    const effectiveType = conn.effectiveType;
    if (effectiveType === '2g' || effectiveType === 'slow-2g') {
      showToast('⚠️ 网络较慢，建议切换清晰度');
    }
  }
}
