// ── Screen Share — works for BOTH professor (admin) and students ───────────────
// Role is set by the page: window.ROLE = 'professor' | 'student'

const socket = io();
let sharing = false;
let shareStream = null;
let frameTimer = null;

// ── Professor side ────────────────────────────────────────────────────────────
const startBtn = document.getElementById('start-share-btn');
const stopBtn  = document.getElementById('stop-share-btn');
const sharingIndicator = document.getElementById('sharing-indicator');

if (startBtn) {
  startBtn.addEventListener('click', async () => {
    try {
      shareStream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 8, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false
      });

      // Hidden video element to capture frames
      const video = document.createElement('video');
      video.srcObject = shareStream;
      video.muted = true;
      await video.play();

      const canvas = document.createElement('canvas');
      const ctx    = canvas.getContext('2d');
      sharing = true;

      startBtn.style.display = 'none';
      stopBtn.style.display  = 'inline-flex';
      if (sharingIndicator) sharingIndicator.classList.add('active');

      socket.emit('sharing_started');

      const sendFrame = () => {
        if (!sharing || video.videoWidth === 0) {
          if (sharing) frameTimer = setTimeout(sendFrame, 150);
          return;
        }
        canvas.width  = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0);
        const frame = canvas.toDataURL('image/jpeg', 0.55);
        socket.emit('screen_frame', frame);
        frameTimer = setTimeout(sendFrame, 130); // ~7-8 fps
      };
      sendFrame();

      // Handle stream ending (user clicks "Stop sharing" in browser UI)
      shareStream.getVideoTracks()[0].addEventListener('ended', stopSharing);

    } catch (err) {
      if (err.name !== 'AbortError' && err.name !== 'NotAllowedError') {
        alert('Could not start screen sharing: ' + err.message);
      }
    }
  });
}

if (stopBtn) {
  stopBtn.addEventListener('click', stopSharing);
}

function stopSharing() {
  sharing = false;
  clearTimeout(frameTimer);
  if (shareStream) {
    shareStream.getTracks().forEach(t => t.stop());
    shareStream = null;
  }
  if (startBtn) startBtn.style.display = 'inline-flex';
  if (stopBtn)  stopBtn.style.display  = 'none';
  if (sharingIndicator) sharingIndicator.classList.remove('active');
  socket.emit('sharing_stopped');
}

// ── Student side ──────────────────────────────────────────────────────────────
const screenImg         = document.getElementById('screen-img');
const screenPlaceholder = document.getElementById('screen-placeholder');
const liveDot           = document.getElementById('live-dot');

socket.on('screen_frame', (dataUrl) => {
  if (!screenImg) return;
  screenImg.src = dataUrl;
  if (!screenImg.classList.contains('active')) {
    screenImg.classList.add('active');
    if (screenPlaceholder) screenPlaceholder.style.display = 'none';
    if (liveDot) liveDot.classList.add('active');
  }
});

socket.on('sharing_started', () => {
  if (liveDot) liveDot.classList.add('active');
  if (screenPlaceholder) {
    screenPlaceholder.innerHTML = '<div class="icon">📡</div><p>Receiving screen — please wait…</p>';
  }
});

socket.on('sharing_stopped', () => {
  if (screenImg) { screenImg.src = ''; screenImg.classList.remove('active'); }
  if (liveDot) liveDot.classList.remove('active');
  if (screenPlaceholder) {
    screenPlaceholder.style.display = 'flex';
    screenPlaceholder.innerHTML = '<div class="icon">🖥️</div><p>Screen sharing has ended.</p>';
  }
});
