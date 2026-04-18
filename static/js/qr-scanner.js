/**
 * 極真館セミナーライブラリ — QRスキャナー
 * カメラを使ってQRコードを読み取り、セミナー出席を記録する
 */

(function () {
  "use strict";

  // --- jsQR をCDNから動的ロード ---
  let jsQRLoaded = false;
  function loadJsQR() {
    return new Promise((resolve, reject) => {
      if (jsQRLoaded || window.jsQR) { jsQRLoaded = true; resolve(); return; }
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js";
      s.onload = () => { jsQRLoaded = true; resolve(); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  // --- モーダル HTML ---
  function createModal() {
    const overlay = document.createElement("div");
    overlay.id = "qr-overlay";
    overlay.innerHTML = `
      <div class="qr-modal">
        <div class="qr-modal-header">
          <h3>QRコードをスキャン</h3>
          <button id="qr-close" aria-label="閉じる">&times;</button>
        </div>
        <div class="qr-video-wrap">
          <video id="qr-video" playsinline autoplay muted></video>
          <div class="qr-guide"></div>
        </div>
        <p id="qr-status" class="qr-status">カメラを起動中...</p>
      </div>
    `;
    document.body.appendChild(overlay);
    return overlay;
  }

  // --- スキャナー本体 ---
  let stream = null;
  let scanning = false;
  let animFrame = null;

  function stopCamera() {
    scanning = false;
    if (animFrame) cancelAnimationFrame(animFrame);
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
  }

  function closeModal() {
    stopCamera();
    const overlay = document.getElementById("qr-overlay");
    if (overlay) overlay.remove();
  }

  async function openScanner() {
    // jsQR をロード
    try {
      await loadJsQR();
    } catch {
      alert("QRスキャンライブラリの読み込みに失敗しました。\nネットワーク接続を確認してください。");
      return;
    }

    const overlay = createModal();
    const video = document.getElementById("qr-video");
    const status = document.getElementById("qr-status");

    document.getElementById("qr-close").addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeModal();
    });

    // カメラ起動
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      video.srcObject = stream;
      await video.play();
      status.textContent = "QRコードをカメラに映してください";
      scanning = true;
      scanLoop(video, status);
    } catch (err) {
      console.error("Camera error:", err);
      if (err.name === "NotAllowedError") {
        status.textContent = "カメラへのアクセスが許可されていません。\n設定からカメラを許可してください。";
      } else {
        status.textContent = "カメラを起動できませんでした。";
      }
    }
  }

  function scanLoop(video, statusEl) {
    if (!scanning) return;

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

      const code = window.jsQR(imageData.data, imageData.width, imageData.height, {
        inversionAttempts: "dontInvert",
      });

      if (code && code.data) {
        const url = code.data;
        // セミナーURLかチェック
        if (isValidSeminarURL(url)) {
          scanning = false;
          statusEl.textContent = "読み取り成功！移動中...";
          statusEl.style.color = "#16a34a";
          stopCamera();
          // 少し待ってから遷移
          setTimeout(() => {
            closeModal();
            navigateToSeminar(url);
          }, 600);
          return;
        }
      }
    }

    animFrame = requestAnimationFrame(() => scanLoop(video, statusEl));
  }

  function isValidSeminarURL(url) {
    try {
      const u = new URL(url);
      // 自サイトの /s/ パスかチェック
      return u.pathname.startsWith("/s/") && (
        u.hostname === location.hostname ||
        u.hostname.includes("kyokushin-seminar") ||
        u.hostname.includes("kyokushinkan")
      );
    } catch {
      return false;
    }
  }

  function navigateToSeminar(url) {
    try {
      const u = new URL(url);
      // 同一オリジンならパスだけ使う（PWA内遷移）
      if (u.hostname === location.hostname) {
        window.location.href = u.pathname;
      } else {
        // カスタムドメイン等で異なる場合は /s/ パスだけ抽出
        window.location.href = u.pathname;
      }
    } catch {
      window.location.href = url;
    }
  }

  // --- 公開 ---
  window.KyokushinQR = { open: openScanner };
})();
