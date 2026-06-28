document.addEventListener("DOMContentLoaded", () => {
    // API base URL - rỗng nghĩa là gọi cùng host phục vụ static files
    const API_BASE = "";

    // --- Utils ---
    function formatVNTime(isoStr, onlyTime = false) {
        if (!isoStr) return "--:--:--";
        try {
            if (!isoStr.endsWith("Z") && !isoStr.includes("+")) isoStr += "Z";
            const d = new Date(isoStr);
            if (isNaN(d.getTime())) return isoStr;
            
            // Cộng thêm 7 tiếng (GMT+7)
            d.setTime(d.getTime() + 7 * 60 * 60 * 1000);
            
            const dd = String(d.getUTCDate()).padStart(2, '0');
            const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
            const yyyy = d.getUTCFullYear();
            
            const hh = String(d.getUTCHours()).padStart(2, '0');
            const mins = String(d.getUTCMinutes()).padStart(2, '0');
            const ss = String(d.getUTCSeconds()).padStart(2, '0');
            
            if (onlyTime) {
                return `${hh}:${mins}:${ss}`;
            }
            return `${dd}/${mm}/${yyyy} ${hh}:${mins}:${ss}`;
        } catch (e) {
            return isoStr;
        }
    }

    // DOM Elements
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    const configForm = document.getElementById("config-form");
    const inboundSignalsFeed = document.getElementById("inbound-signals-feed");
    const btnSimulateB6 = document.getElementById("btn-simulate-b6");
    const logsFeedContainer = document.getElementById("logs-feed-container");
    const btnRefresh = document.getElementById("btn-refresh");
    const toastContainer = document.getElementById("toast-container");
    
    // Filters
    const searchInput = document.getElementById("log-search");
    const filterSeverity = document.getElementById("filter-severity");
    const filterChannel = document.getElementById("filter-channel");

    // Metrics elements
    const metricTotal = document.getElementById("metric-total");
    const metricSuccess = document.getElementById("metric-success");
    const metricSuccessRate = document.getElementById("metric-success-rate");
    const metricDedup = document.getElementById("metric-dedup");
    const metricRetry = document.getElementById("metric-retry");

    // Modal elements
    const logModal = document.getElementById("log-modal");
    const modalJson = document.getElementById("modal-json");
    const closeModal = document.querySelector(".close-modal");

    // Mock switches for toggling field displays
    const mockTelegram = document.getElementById("cfg-mock-telegram");
    const mockDiscord = document.getElementById("cfg-mock-discord");
    const mockEmail = document.getElementById("cfg-mock-email");

    // --- Tab Switching Logic ---
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            
            // Xóa active cũ
            tabBtns.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));

            // Active mới
            btn.classList.add("active");
            document.getElementById(targetTab).classList.add("active");

            if (targetTab === "tab-config") {
                fetchChannelConfigs();
            }
        });
    });

    // --- Dynamic Fields Visibility in Config tab ---
    function toggleConfigFields() {
        // Telegram Fields
        const tgFields = document.querySelector(".config-fields-telegram");
        if (mockTelegram.checked) {
            tgFields.style.opacity = "0.5";
            tgFields.querySelectorAll("input").forEach(i => i.disabled = true);
        } else {
            tgFields.style.opacity = "1";
            tgFields.querySelectorAll("input").forEach(i => i.disabled = false);
        }

        // Discord Fields
        const discordFields = document.querySelector(".config-fields-discord");
        if (mockDiscord.checked) {
            discordFields.style.opacity = "0.5";
            discordFields.querySelectorAll("input").forEach(i => i.disabled = true);
        } else {
            discordFields.style.opacity = "1";
            discordFields.querySelectorAll("input").forEach(i => i.disabled = false);
        }

        // Email Fields
        const emailFields = document.querySelectorAll(".config-fields-email");
        emailFields.forEach(block => {
            if (mockEmail.checked) {
                block.style.opacity = "0.5";
                block.querySelectorAll("input").forEach(i => i.disabled = true);
            } else {
                block.style.opacity = "1";
                block.querySelectorAll("input").forEach(i => i.disabled = false);
            }
        });
    }

    [mockTelegram, mockDiscord, mockEmail].forEach(sw => {
        sw.addEventListener("change", toggleConfigFields);
    });

    // --- Toast Notifications helper ---
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        let icon = "fa-circle-info";
        if (type === "success") icon = "fa-circle-check";
        if (type === "error") icon = "fa-circle-exclamation";
        if (type === "warning") icon = "fa-triangle-exclamation";

        toast.innerHTML = `
            <i class="fa-solid ${icon} toast-icon"></i>
            <span class="toast-message">${message}</span>
        `;
        
        toastContainer.appendChild(toast);
        
        // Tự động xóa toast sau 4 giây
        setTimeout(() => {
            toast.style.animation = "fadeOut 0.5s forwards";
            toast.addEventListener("animationend", () => {
                toast.remove();
            });
        }, 4000);
    }

    // --- API Interactions ---

    // 1. Fetch channel config
    async function fetchChannelConfigs() {
        try {
            const response = await fetch(`${API_BASE}/api/v1/channels`);
            if (!response.ok) throw new Error("Không thể tải cấu hình kênh");
            
            const data = await response.json();
            const config = data.global_settings;
            const chan = data.channels;

            // Điền global settings
            document.getElementById("cfg-dedup-ttl").value = config.deduplication_ttl;
            document.getElementById("cfg-retry-limit").value = config.retry_limit;
            document.getElementById("cfg-retry-delay").value = config.retry_delay;

            // Điền mocks switches
            mockTelegram.checked = chan.telegram.mocked;
            mockDiscord.checked = chan.discord.mocked;
            mockEmail.checked = chan.email.mocked;

            // Lấy toàn bộ config thô để hiển thị credentials
            const rawResponse = await fetch(`${API_BASE}/api/v1/channels`);
            const rawData = await rawResponse.json();
            
            // Cập nhật giá trị
            document.getElementById("cfg-tg-chat").value = chan.telegram.target_detail !== "Not configured" ? chan.telegram.target_detail : "";
            document.getElementById("cfg-smtp-receiver").value = chan.email.target_detail !== "Not configured" ? chan.email.target_detail : "";

            toggleConfigFields();
        } catch (error) {
            showToast(error.message, "error");
        }
    }

    // 2. Submit config update
    configForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const formData = new FormData(configForm);
        const payload = {};

        // Chuyển dữ liệu form thành JSON object đúng định dạng
        for (const [key, value] of formData.entries()) {
            if (key.startsWith("MOCK_")) {
                payload[key] = true;
            } else if (key === "DEDUPLICATION_TTL_SECONDS" || key === "RETRY_MAX_LIMIT" || key === "RETRY_DELAY_SECONDS" || key === "SMTP_PORT") {
                payload[key] = parseInt(value);
            } else {
                payload[key] = value;
            }
        }

        // Với checkbox Mock không được check thì gửi giá trị false
        ["MOCK_TELEGRAM", "MOCK_DISCORD", "MOCK_EMAIL"].forEach(key => {
            if (!payload[key]) payload[key] = false;
        });

        try {
            const response = await fetch(`${API_BASE}/api/v1/channels/configure`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error("Cập nhật cấu hình thất bại");

            showToast("Cập nhật cấu hình thành công!", "success");
            fetchChannelConfigs();
        } catch (error) {
            showToast(error.message, "error");
        }
    });

    // --- B6 Inbound Signals Logic ---
    async function fetchInboundSignals() {
        try {
            const response = await fetch(`${API_BASE}/analytics/inbound/signals`);
            if (!response.ok) throw new Error("Không thể tải danh sách tín hiệu B6");
            const signals = await response.json();
            renderInboundSignals(signals);
        } catch (error) {
            console.error("Lỗi đồng bộ tín hiệu inbound:", error);
        }
    }

    function renderInboundSignals(signals) {
        if (!inboundSignalsFeed) return;
        if (signals.length === 0) {
            inboundSignalsFeed.innerHTML = `
                <div class="empty-logs" style="padding: 2rem 0; text-align: center;">
                    <i class="fa-solid fa-satellite-dish" style="font-size: 2rem; opacity: 0.3; margin-bottom: 0.5rem; display: block;"></i>
                    <p style="opacity: 0.5; font-size: 0.9rem;">Chưa nhận được tín hiệu nào từ B6. Bấm nút giả lập bên dưới để demo nhanh!</p>
                </div>
            `;
            return;
        }

        inboundSignalsFeed.innerHTML = signals.map(sig => {
            const style = getAlertStyles(sig.details && sig.details.message ? sig.details.message : sig.log_type);
            
            let detailsHtml = `
                <div style="font-size: 0.8rem; margin: 4px 0; opacity: 0.8;">
                    <strong>Tiêu đề:</strong> ${sig.details?.title || 'N/A'} <br/>
                    <strong>Mức độ:</strong> <span style="color: #ff7675; font-weight: bold;">${sig.details?.level || 'N/A'}</span>
                </div>
            `;

            return `
                <div class="log-item" style="${style.border} background: ${style.bg};" data-timestamp="${sig.timestamp}">
                    <div class="log-header">
                        <div class="log-id-group">
                            <span class="log-id" style="display:flex;align-items:center;gap:6px;">
                                <i class="${style.icon}"></i> ${sig.log_type}
                            </span>
                            <span class="status-badge ${sig.status}">
                                <i class="fa-solid fa-bell"></i> ${sig.reason || 'Đã phát thông báo'}
                            </span>
                        </div>
                    </div>
                    ${detailsHtml}
                    <div class="log-body" style="font-size: 0.85rem; margin-top: 4px;">${sig.details?.message || ''}</div>
                    <div class="log-footer">
                        <span class="log-time"><i class="fa-regular fa-clock"></i> ${formatVNTime(sig.timestamp, true)}</span>
                    </div>
                </div>
            `;
        }).join("");
    }




    // --- Sound Notification Setup (Web Audio API) ---
    let soundEnabled = true;
    let sharedAudioCtx = null;

    function initSharedAudio() {
        if (!sharedAudioCtx) {
            sharedAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (sharedAudioCtx && sharedAudioCtx.state === 'suspended') {
            sharedAudioCtx.resume();
        }
    }

    // Activate the shared AudioContext on first click anywhere on the document
    document.addEventListener("click", initSharedAudio, { once: true });

    function playSiren() {
        if (!soundEnabled) return;
        try {
            initSharedAudio();
            if (!sharedAudioCtx) return;

            const osc = sharedAudioCtx.createOscillator();
            const gainNode = sharedAudioCtx.createGain();
            
            osc.connect(gainNode);
            gainNode.connect(sharedAudioCtx.destination);
            
            osc.type = 'sine';
            const now = sharedAudioCtx.currentTime;
            
            // Sweep frequency back and forth over 3.0 seconds
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.linearRampToValueAtTime(880, now + 0.5);
            osc.frequency.linearRampToValueAtTime(440, now + 1.0);
            osc.frequency.linearRampToValueAtTime(880, now + 1.5);
            osc.frequency.linearRampToValueAtTime(440, now + 2.0);
            osc.frequency.linearRampToValueAtTime(880, now + 2.5);
            osc.frequency.linearRampToValueAtTime(440, now + 3.0);
            
            // Apply volume fade-in and fade-out
            gainNode.gain.setValueAtTime(0, now);
            gainNode.gain.linearRampToValueAtTime(0.4, now + 0.1);
            gainNode.gain.setValueAtTime(0.4, now + 2.8);
            gainNode.gain.linearRampToValueAtTime(0, now + 3.0);
            
            osc.start(now);
            osc.stop(now + 3.0);
        } catch (err) {
            console.warn("Could not play synthesized audio alarm:", err);
        }
    }

    function playShortBeep() {
        try {
            initSharedAudio();
            if (!sharedAudioCtx) return;

            const osc = sharedAudioCtx.createOscillator();
            const gainNode = sharedAudioCtx.createGain();
            
            osc.connect(gainNode);
            gainNode.connect(sharedAudioCtx.destination);
            
            osc.frequency.setValueAtTime(600, sharedAudioCtx.currentTime);
            gainNode.gain.setValueAtTime(0.1, sharedAudioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, sharedAudioCtx.currentTime + 0.15);
            
            osc.start();
            osc.stop(sharedAudioCtx.currentTime + 0.15);
        } catch (e) {}
    }

    function checkAndPlayAlarm(newLogs) {
        if (cachedLogs.length === 0) return; // Do not alert on initial load
        
        // Find if there are new alerts with CRITICAL or HIGH severity
        const hasNewCritical = newLogs.some(log => {
            const isNew = !cachedLogs.some(old => old.ticket_id === log.ticket_id);
            return isNew && (log.severity === "CRITICAL" || log.severity === "HIGH");
        });

        if (hasNewCritical) {
            playSiren();
            showToast("🚨 PHÁT HIỆN CẢNH BÁO NGUY HIỂM MỚI!", "warning");
        }
    }

    // Toggle Sound Button handler
    const btnToggleSound = document.getElementById("btn-toggle-sound");
    const soundIcon = document.getElementById("sound-icon");
    const soundStatus = document.getElementById("sound-status");

    if (btnToggleSound) {
        btnToggleSound.addEventListener("click", () => {
            soundEnabled = !soundEnabled;
            if (soundEnabled) {
                soundIcon.className = "fa-solid fa-volume-high";
                soundStatus.innerText = "Âm thanh: Bật";
                btnToggleSound.style.background = ""; // Reset to CSS default
                btnToggleSound.style.color = ""; // Reset to CSS default
                playShortBeep(); // user interaction enables Web Audio
            } else {
                soundIcon.className = "fa-solid fa-volume-xmark";
                soundStatus.innerText = "Âm thanh: Tắt";
                btnToggleSound.style.background = "rgba(235, 77, 75, 0.15)";
                btnToggleSound.style.color = "var(--danger)";
            }
        });
    }

    // --- Dynamic Detail Pane View ---
    let selectedLog = null;

    function showLogDetail(log) {
        selectedLog = log;
        
        // Remove active class from all other log items, and add to current
        document.querySelectorAll("#logs-feed-container .log-item").forEach(item => {
            const isMatch = log && 
                            item.getAttribute("data-log-id") === log.alert_id && 
                            item.getAttribute("data-channel") === log.channel && 
                            item.getAttribute("data-timestamp") === log.timestamp;
            if (isMatch) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        const detailContainer = document.getElementById("log-detail-container");
        if (!detailContainer) return;

        if (!log) {
            detailContainer.innerHTML = `
                <div class="empty-detail">
                    <i class="fa-solid fa-circle-info"></i>
                    <p>Chọn một bản ghi nhật ký bên trái để xem chi tiết gửi tin và dữ liệu thô (JSON).</p>
                </div>
            `;
            return;
        }

        let channelIcon = "fa-solid fa-bell";
        if (log.channel === "telegram") channelIcon = "fa-brands fa-telegram text-blue";
        if (log.channel === "discord") channelIcon = "fa-brands fa-discord text-purple";
        if (log.channel === "email") channelIcon = "fa-solid fa-envelope text-red";
        if (log.channel === "sms") channelIcon = "fa-solid fa-comment-sms";
        if (log.channel === "zalo") channelIcon = "fa-solid fa-square-phone";

        const style = getAlertStyles(log.message);

        detailContainer.innerHTML = `
            <div class="detail-card" style="animation: fadeIn var(--transition-fast);">
                <div class="detail-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem; border-bottom:1px solid var(--border-color); padding-bottom:0.75rem;">
                    <h3 style="font-family:var(--font-heading); font-size:1.15rem; display:flex; align-items:center; gap:8px; margin:0; color:var(--text-primary);">
                        <i class="${style.icon}"></i> ${style.title}
                    </h3>
                    <span class="severity-badge ${log.severity}" style="font-size:0.7rem; font-weight:700; padding:0.15rem 0.45rem; border-radius:4px; margin:0;">${log.severity}</span>
                </div>
                
                <div class="detail-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; margin-bottom:1.25rem;">
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:8px; padding:0.5rem 0.75rem;">
                        <div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:2px;">Kênh Truyền Tải</div>
                        <div style="font-size:0.85rem; font-weight:600; display:flex; align-items:center; gap:6px; color:var(--text-primary);">
                            <i class="${channelIcon}"></i> ${log.channel.toUpperCase()}
                        </div>
                    </div>
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:8px; padding:0.5rem 0.75rem;">
                        <div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:2px;">Trạng Thái</div>
                        <span class="status-badge ${log.status}" style="font-size:0.72rem; font-weight:600; padding:0.15rem 0.5rem; border-radius:50px; display:inline-flex; align-items:center; gap:4px; width:fit-content; border: 1px solid; margin:0;">
                            <i class="fa-solid ${log.sent ? 'fa-check-circle' : 'fa-circle-xmark'}"></i>
                            ${log.status.replace('_', ' ').toUpperCase()}
                        </span>
                    </div>
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:8px; padding:0.5rem 0.75rem;">
                        <div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:2px;">Thời Gian Ghi Nhận</div>
                        <div style="font-size:0.82rem; font-weight:500; color:var(--text-primary);">
                            <i class="fa-regular fa-clock" style="margin-right:2px; font-size:0.8rem;"></i> ${formatVNTime(log.timestamp, false)}
                        </div>
                    </div>
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:8px; padding:0.5rem 0.75rem;">
                        <div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:2px;">Số Lần Thử</div>
                        <div style="font-size:0.85rem; font-weight:600; color:${log.retry_count > 0 ? 'var(--warning)' : 'var(--text-primary)'};">
                            <i class="fa-solid fa-arrows-rotate" style="margin-right:2px; font-size:0.8rem;"></i> ${log.retry_count} lần thử
                        </div>
                    </div>
                </div>
                
                <div class="detail-section" style="margin-bottom:1.25rem;">
                    <h4 style="font-size:0.8rem; font-weight:700; color:var(--text-muted); margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.05em; margin-top:0;">Thông điệp cảnh báo</h4>
                    <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:8px; padding:0.85rem 1rem; font-size:0.875rem; line-height:1.4; color:var(--text-primary); border-left:3px solid var(--accent);">${log.message}</div>
                </div>

                <div class="detail-section" style="margin-bottom:1.25rem;">
                    <h4 style="font-size:0.8rem; font-weight:700; color:var(--text-muted); margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.05em; margin-top:0;">Thông tin định danh</h4>
                    <div style="display:flex; flex-direction:column; gap:4px; font-size:0.78rem; background:rgba(0,0,0,0.02); padding:0.6rem 0.85rem; border-radius:8px; border:1px solid var(--border-color); font-family:monospace; word-break:break-all; color:var(--text-primary);">
                        <div><strong>Event ID:</strong> <span style="opacity:0.85;">${log.event_id || 'N/A'}</span></div>
                        <div><strong>Alert ID:</strong> <span style="opacity:0.85;">${log.alert_id || 'N/A'}</span></div>
                        <div><strong>Ticket ID:</strong> <span style="opacity:0.85;">${log.ticket_id || 'N/A'}</span></div>
                        ${log.error_message ? `<div style="color:var(--danger); margin-top:4px; word-break:break-word;"><strong>Lỗi kỹ thuật:</strong> <span>${log.error_message}</span></div>` : ''}
                    </div>
                </div>
                
                <div class="detail-section">
                    <h4 style="font-size:0.8rem; font-weight:700; color:var(--text-muted); margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.05em; margin-top:0;">Dữ liệu thô (JSON)</h4>
                    <pre class="json-display" style="font-size:0.78rem; max-height:220px; overflow-y:auto; padding:0.75rem 1rem; background:#05070c; border-radius:8px; border:1px solid var(--border-color); color:#a7f3d0; margin-top:0.25rem;"><code style="font-family:monospace; line-height:1.35;">${JSON.stringify(log, null, 4)}</code></pre>
                </div>
            </div>
        `;
    }

    // 4. Fetch Logs and Update Metrics
    let cachedLogs = [];

    async function fetchLogs() {
        try {
            const response = await fetch(`${API_BASE}/api/v1/alerts/logs?limit=50`);
            if (!response.ok) throw new Error("Không thể tải nhật ký");

            const logs = await response.json();
            
            // Check if any new CRITICAL or HIGH logs need to be announced
            checkAndPlayAlarm(logs);

            cachedLogs = logs;
            renderLogs();
            updateMetrics(logs);
        } catch (error) {
            console.error("Lỗi đồng bộ logs:", error);
        }
    }

    function getAlertStyles(message) {
        if (!message) message = "";
        const msg = message.toLowerCase();
        
        if (msg.includes("uid") || msg.includes("thẻ lạ") || msg.includes("thẻ lậu") || msg.includes("chưa đăng ký")) {
            return { icon: "fa-solid fa-id-card-clip text-orange", border: "border-left: 4px solid #e17055;", title: "Sự Cố Cổng An Ninh (B3)", bg: "rgba(225, 112, 85, 0.05)" };
        }
        if (msg.includes("hỏa hoạn") || msg.includes("nhiệt độ") || msg.includes("khói")) {
            return { icon: "fa-solid fa-fire text-red", border: "border-left: 4px solid #d63031;", title: "Cảnh Báo Hỏa Hoạn (B1)", bg: "rgba(214, 48, 49, 0.05)" };
        }
        if (msg.includes("thiết bị lạ") || msg.includes("xâm nhập") || msg.includes("unknown")) {
            return { icon: "fa-solid fa-shield-virus text-purple", border: "border-left: 4px solid #9b59b6;", title: "Xâm Nhập Mạng IoT (B1)", bg: "rgba(155, 89, 182, 0.05)" };
        }
        if (msg.includes("ai vision") || msg.includes("camera") || msg.includes("vũ khí")) {
            return { icon: "fa-solid fa-camera text-red", border: "border-left: 4px solid #e84393;", title: "Phát Hiện Rủi Ro AI (B4)", bg: "rgba(232, 67, 147, 0.05)" };
        }
        return { icon: "fa-solid fa-circle-exclamation text-blue", border: "border-left: 4px solid #0984e3;", title: "Cảnh Báo Hệ Thống", bg: "rgba(255, 255, 255, 0.02)" };
    }

    function updateMetrics(logs) {
        let total = logs.length;
        let success = 0;
        let dedup = 0;
        let retrySum = 0;

        logs.forEach(log => {
            if (log.sent) success++;
            if (log.status === "duplicate_ignored") dedup++;
            // Tính tổng số lượt retry của tất cả các cảnh báo (kể cả thành công sau khi retry)
            if (log.retry_count > 0 && log.status !== "duplicate_ignored") {
                retrySum += log.retry_count;
            }
        });

        metricTotal.innerText = total;
        metricSuccess.innerText = success;
        metricDedup.innerText = dedup;
        metricRetry.innerText = retrySum;

        // Tính tỷ lệ thành công (không tính các alert bị chặn trùng từ đầu)
        const validAttempts = total - dedup;
        const rate = validAttempts > 0 ? Math.round((success / validAttempts) * 100) : 0;
        metricSuccessRate.innerText = `Tỷ lệ thành công: ${rate}%`;
    }

    function renderLogs() {
        const searchQuery = searchInput.value.toLowerCase().trim();
        const severityFilter = filterSeverity.value;
        const channelFilter = filterChannel.value;

        // Lọc log theo giao diện người dùng
        const filtered = cachedLogs.filter(log => {
            const matchesSearch = log.alert_id.toLowerCase().includes(searchQuery) || 
                                  (log.event_id && log.event_id.toLowerCase().includes(searchQuery)) || 
                                  log.message.toLowerCase().includes(searchQuery);
            const matchesSeverity = !severityFilter || log.severity.toLowerCase() === severityFilter.toLowerCase();
            const matchesChannel = !channelFilter || log.channel.toLowerCase() === channelFilter.toLowerCase();
            return matchesSearch && matchesSeverity && matchesChannel;
        });

        if (filtered.length === 0) {
            logsFeedContainer.innerHTML = `
                <div class="empty-logs">
                    <i class="fa-solid fa-square-poll-horizontal"></i>
                    <p>Không tìm thấy kết quả phù hợp với bộ lọc hiện tại.</p>
                </div>
            `;
            showLogDetail(null);
            return;
        }

        logsFeedContainer.innerHTML = filtered.map(log => {
            let channelIcon = "fa-solid fa-bell";
            if (log.channel === "telegram") channelIcon = "fa-brands fa-telegram text-blue";
            if (log.channel === "discord") channelIcon = "fa-brands fa-discord text-purple";
            if (log.channel === "email") channelIcon = "fa-solid fa-envelope text-red";
            if (log.channel === "sms") channelIcon = "fa-solid fa-comment-sms";
            if (log.channel === "zalo") channelIcon = "fa-solid fa-square-phone";

            const retryHtml = (log.retry_count > 0 && !log.sent) ? `
                <span class="retry-indicator">
                    <i class="fa-solid fa-arrows-rotate fa-spin"></i> Retry: ${log.retry_count}
                </span>
            ` : "";

            const style = getAlertStyles(log.message);

            return `
                <div class="log-item" style="${style.border} background: ${style.bg};" data-log-id="${log.alert_id}" data-timestamp="${log.timestamp}" data-channel="${log.channel}">
                    <div class="log-header">
                        <div class="log-id-group">
                            <span class="log-id" style="display:flex;align-items:center;gap:6px;" title="Event ID: ${log.event_id || 'N/A'}">
                                <i class="${style.icon}"></i> ${style.title}
                            </span>
                            <span class="severity-badge ${log.severity}">${log.severity}</span>
                        </div>
                        <div class="log-meta">
                            <span class="channel-tag">
                                <i class="${channelIcon}"></i> ${log.channel.toUpperCase()}
                            </span>
                            <span class="status-badge ${log.status}">
                                <i class="fa-solid ${log.sent ? 'fa-check-circle' : 'fa-circle-xmark'}"></i>
                                ${log.status.replace('_', ' ')}
                            </span>
                        </div>
                    </div>
                    <div class="log-body">${log.message}</div>
                    <div class="log-footer">
                        <span class="log-time"><i class="fa-regular fa-clock"></i> ${formatVNTime(log.timestamp, false)}</span>
                        <span class="ticket-tag" style="font-family: monospace; font-size: 0.72rem; opacity: 0.6;" title="Ticket ID: ${log.ticket_id}">
                            <i class="fa-solid fa-ticket"></i> Ticket: ${log.ticket_id.substring(0, 8)}...
                        </span>
                        ${retryHtml}
                    </div>
                </div>
            `;

        }).join("");

        // Gắn sự kiện click để hiển thị chi tiết log bên phải
        document.querySelectorAll("#logs-feed-container .log-item").forEach(item => {
            item.addEventListener("click", () => {
                const alertId = item.getAttribute("data-log-id");
                const channel = item.getAttribute("data-channel");
                const timestamp = item.getAttribute("data-timestamp");
                const log = cachedLogs.find(l => l.alert_id === alertId && l.channel === channel && l.timestamp === timestamp);
                if (log) {
                    showLogDetail(log);
                }
            });
        });

        // Tự động chọn log để hiển thị chi tiết (giữ nguyên lựa chọn cũ nếu còn, hoặc chọn phần tử đầu tiên)
        let activeLog = null;
        if (selectedLog) {
            activeLog = filtered.find(l => l.alert_id === selectedLog.alert_id && l.channel === selectedLog.channel && l.timestamp === selectedLog.timestamp);
        }
        if (!activeLog) {
            activeLog = filtered[0];
        }
        showLogDetail(activeLog);
    }

    // Gắn sự kiện lọc dữ liệu tức thì
    searchInput.addEventListener("input", renderLogs);
    filterSeverity.addEventListener("change", renderLogs);
    filterChannel.addEventListener("change", renderLogs);

    // Refresh logs thủ công
    btnRefresh.addEventListener("click", () => {
        showToast("Đang đồng bộ dữ liệu...", "info");
        fetchLogs();
        fetchInboundSignals();
    });

    // --- Modal Logic ---
    closeModal.addEventListener("click", () => {
        logModal.classList.remove("open");
    });

    window.addEventListener("click", (e) => {
        if (e.target === logModal) {
            logModal.classList.remove("open");
        }
    });

    // =============================================================
    // REAL-TIME: Server-Sent Events (SSE)
    // Kết nối tới /events/stream — nhận push ngay khi B6 gửi data
    // =============================================================
    let sseRetryCount = 0;
    const MAX_SSE_RETRY = 10;
    const statusIndicator = document.querySelector(".status-indicator");
    const statusLabel = document.querySelector(".status-label");

    function setConnectionStatus(state) {
        if (state === "connected") {
            statusIndicator.className = "status-indicator online";
            statusLabel.textContent = "Live ● Real-time";
            statusLabel.style.color = "#55efc4";
        } else if (state === "reconnecting") {
            statusIndicator.className = "status-indicator";
            statusIndicator.style.background = "#fdcb6e";
            statusLabel.textContent = "Đang kết nối lại...";
            statusLabel.style.color = "#fdcb6e";
        } else {
            statusIndicator.className = "status-indicator";
            statusIndicator.style.background = "#ff7675";
            statusLabel.textContent = "Mất kết nối Real-time";
            statusLabel.style.color = "#ff7675";
        }
    }

    function prependInboundCard(sig) {
        if (!inboundSignalsFeed) return;
        // Xoá màn hình empty nếu còn
        const emptyEl = inboundSignalsFeed.querySelector(".empty-logs");
        if (emptyEl) emptyEl.remove();

        const style = getAlertStyles(sig.details && sig.details.message ? sig.details.message : sig.log_type);
        
        let detailsHtml = `
            <div style="font-size: 0.8rem; margin: 4px 0; opacity: 0.8;">
                <strong>Tiêu đề:</strong> ${sig.details?.title || 'N/A'} <br/>
                <strong>Mức độ:</strong> <span style="color: #ff7675; font-weight: bold;">${sig.details?.level || 'N/A'}</span>
            </div>
        `;

        const card = document.createElement("div");
        card.className = "log-item";
        card.style.cssText = `${style.border} background: ${style.bg}; animation: slideInNew 0.4s ease-out;`;
        card.innerHTML = `
            <div class="log-header">
                <div class="log-id-group">
                    <span class="log-id" style="display:flex;align-items:center;gap:6px;">
                        <i class="${style.icon}"></i> ${sig.log_type}
                        <span style="background:rgba(0,206,201,0.2);color:#00cec9;font-size:0.65rem;padding:1px 5px;border-radius:10px;font-weight:600;letter-spacing:0.05em;">LIVE</span>
                    </span>
                    <span class="status-badge ${sig.status}">
                        <i class="fa-solid fa-bell"></i> ${sig.reason || 'Đã phát thông báo'}
                    </span>
                </div>
            </div>
            ${detailsHtml}
            <div class="log-body" style="font-size: 0.85rem; margin-top: 4px;">${sig.details?.message || ''}</div>
            <div class="log-footer">
                <span class="log-time"><i class="fa-regular fa-clock"></i> ${formatVNTime(sig.timestamp, true)}</span>
            </div>
        `;

        inboundSignalsFeed.insertBefore(card, inboundSignalsFeed.firstChild);

        // Giới hạn tối đa 50 card để tránh DOM phình to
        const cards = inboundSignalsFeed.querySelectorAll("div:not(.empty-logs)");
        if (cards.length > 50) cards[cards.length - 1].remove();
    }

    function prependLogCard(log) {
        if (!logsFeedContainer) return;
        const emptyEl = logsFeedContainer.querySelector(".empty-logs");
        if (emptyEl) emptyEl.remove();

        let channelIcon = "fa-solid fa-bell";
        if (log.channel === "telegram") channelIcon = "fa-brands fa-telegram text-blue";
        if (log.channel === "discord") channelIcon = "fa-brands fa-discord text-purple";
        if (log.channel === "email") channelIcon = "fa-solid fa-envelope text-red";
        if (log.channel === "sms") channelIcon = "fa-solid fa-comment-sms";
        if (log.channel === "zalo") channelIcon = "fa-solid fa-square-phone";

        const retryHtml = (log.retry_count > 0 && !log.sent) ? `
            <span class="retry-indicator">
                <i class="fa-solid fa-arrows-rotate fa-spin"></i> Retry: ${log.retry_count}
            </span>` : "";

        const style = getAlertStyles(log.message);

        const card = document.createElement("div");
        card.className = "log-item";
        card.setAttribute("data-log-id", log.alert_id);
        card.setAttribute("data-timestamp", log.timestamp);
        card.setAttribute("data-channel", log.channel);
        card.style.cssText = `${style.border} background: ${style.bg}; animation: slideInNew 0.4s ease-out;`;
        card.innerHTML = `
            <div class="log-header">
                <div class="log-id-group">
                    <span class="log-id" style="display:flex;align-items:center;gap:6px;" title="Event ID: ${log.event_id || "N/A"}">
                        <i class="${style.icon}"></i> ${style.title}
                    </span>
                    <span class="severity-badge ${log.severity}">${log.severity}</span>
                    <span style="background:rgba(0,206,201,0.2);color:#00cec9;font-size:0.65rem;padding:1px 5px;border-radius:10px;font-weight:600;letter-spacing:0.05em;">LIVE</span>
                </div>
                <div class="log-meta">
                    <span class="channel-tag"><i class="${channelIcon}"></i> ${log.channel.toUpperCase()}</span>
                    <span class="status-badge ${log.status}">
                        <i class="fa-solid ${log.sent ? "fa-check-circle" : "fa-circle-xmark"}"></i>
                        ${log.status.replace("_", " ")}
                    </span>
                </div>
            </div>
            <div class="log-body">${log.message}</div>
            <div class="log-footer">
                <span class="log-time"><i class="fa-regular fa-clock"></i> ${formatVNTime(log.timestamp, false)}</span>
                <span class="ticket-tag" style="font-family:monospace;font-size:0.72rem;opacity:0.6;" title="Ticket ID: ${log.ticket_id}">
                    <i class="fa-solid fa-ticket"></i> Ticket: ${log.ticket_id.substring(0, 8)}...
                </span>
                ${retryHtml}
            </div>`;

        card.addEventListener("click", () => {
            showLogDetail(log);
        });

        logsFeedContainer.insertBefore(card, logsFeedContainer.firstChild);

        // Cập nhật cache và metrics
        cachedLogs.unshift(log);
        if (cachedLogs.length > 100) cachedLogs.pop();
        updateMetrics(cachedLogs);

        // Hiển thị chi tiết của log mới nhận được luôn
        showLogDetail(log);

        // Giới hạn DOM
        const allCards = logsFeedContainer.querySelectorAll(".log-item");
        if (allCards.length > 50) allCards[allCards.length - 1].remove();
    }

    function connectSSE() {
        const evtSource = new EventSource(`${API_BASE}/events/stream`);

        evtSource.addEventListener("connected", () => {
            setConnectionStatus("connected");
            sseRetryCount = 0;
            console.log("[SSE] Kết nối thành công. Đang chờ push từ B6...");
        });

        // Nhận notification log mới (B6 gửi alert vào /notifications/events)
        evtSource.addEventListener("notification_log", (e) => {
            try {
                const log = JSON.parse(e.data);
                // Kiểm tra trùng trước khi prepend
                const exists = cachedLogs.some(l => l.ticket_id === log.ticket_id);
                if (!exists) {
                    checkAndPlayAlarm([log]);
                    prependLogCard(log);
                    if (log.severity === "CRITICAL" || log.severity === "HIGH") {
                        showToast(`🚨 [B6] Cảnh báo ${log.severity}: ${log.message}`, "warning");
                    } else {
                        showToast(`🔔 [B6] Alert mới: ${log.message}`, "info");
                    }
                }
            } catch (err) {
                console.error("[SSE] Lỗi parse notification_log:", err);
            }
        });

        // Nhận inbound signal mới (B6 gửi vào /analytics/export)
        evtSource.addEventListener("inbound_signal", (e) => {
            try {
                const sig = JSON.parse(e.data);
                prependInboundCard(sig);
                const label = sig.log_type === "FIRE_ALARM" ? "🔥 Cảnh báo cháy" : `🚪 Quẹt thẻ ${sig.details?.action || ""}`;
                showToast(`[B6 Realtime] ${label}`, sig.log_type === "FIRE_ALARM" ? "warning" : "info");
            } catch (err) {
                console.error("[SSE] Lỗi parse inbound_signal:", err);
            }
        });

        evtSource.onerror = () => {
            evtSource.close();
            setConnectionStatus("reconnecting");
            sseRetryCount++;
            if (sseRetryCount <= MAX_SSE_RETRY) {
                const delay = Math.min(3000 * sseRetryCount, 30000);
                console.warn(`[SSE] Mất kết nối. Thử lại sau ${delay / 1000}s... (lần ${sseRetryCount})`);
                setTimeout(connectSSE, delay);
            } else {
                setConnectionStatus("offline");
                showToast("❌ Không thể kết nối SSE. Chuyển sang chế độ polling.", "error");
                // Fallback: polling mỗi 5 giây khi SSE thất bại
                setInterval(() => { fetchLogs(); fetchInboundSignals(); }, 5000);
            }
        };
    }

    // --- Khởi động ứng dụng ---
    fetchLogs();
    fetchInboundSignals();
    fetchChannelConfigs();

    // Khởi động SSE real-time stream
    connectSSE();

    // Polling nhẹ mỗi 30 giây như backup (đồng bộ dữ liệu lịch sử khi mở tab mới)
    setInterval(() => {
        fetchLogs();
        fetchInboundSignals();
    }, 30000);
});
