document.addEventListener("DOMContentLoaded", () => {
    // API base URL - rỗng nghĩa là gọi cùng host phục vụ static files
    const API_BASE = "";

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
            const isFire = sig.log_type === "FIRE_ALARM";
            const isDenied = sig.log_type === "ACCESS" && sig.details.action === "DENIED";
            let statusBadge = "";
            let cardBorder = "border-left: 4px solid #00cec9;";
            let logTypeIcon = "fa-solid fa-id-card";
            let detailsHtml = "";

            if (isFire) {
                cardBorder = "border-left: 4px solid #d63031;";
                logTypeIcon = "fa-solid fa-fire text-red";
                detailsHtml = `
                    <div style="font-size: 0.8rem; margin: 4px 0; opacity: 0.8;">
                        <strong>Thiết bị:</strong> ${sig.details.device_id} | 
                        <strong>Vị trí:</strong> ${sig.details.location} | 
                        <strong>Nhiệt độ:</strong> <span style="color: #ff7675; font-weight: bold;">${sig.details.temperature}°C</span>
                    </div>
                `;
            } else {
                if (isDenied) {
                    cardBorder = "border-left: 4px solid #e17055;";
                    logTypeIcon = "fa-solid fa-user-xmark text-orange";
                } else {
                    logTypeIcon = "fa-solid fa-user-check text-green";
                }
                detailsHtml = `
                    <div style="font-size: 0.8rem; margin: 4px 0; opacity: 0.8;">
                        <strong>Mã SV:</strong> ${sig.details.student_id} | 
                        <strong>Lớp:</strong> ${sig.details.class_name || 'N/A'} |
                        <strong>Cổng:</strong> ${sig.details.gate_id} | 
                        <strong>Hành động:</strong> 
                        <span style="font-weight: bold; color: ${isDenied ? '#ff7675' : '#55efc4'}">${sig.details.action}</span>
                    </div>
                `;
            }

            if (sig.status === "triggered") {
                statusBadge = `<span style="background: rgba(85, 239, 196, 0.15); color: #55efc4; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;"><i class="fa-solid fa-bell"></i> Phát thông báo</span>`;
            } else if (sig.status === "duplicate") {
                statusBadge = `<span style="background: rgba(253, 203, 110, 0.15); color: #fdc12c; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;"><i class="fa-solid fa-clone"></i> Bỏ qua (Trùng)</span>`;
            } else {
                statusBadge = `<span style="background: rgba(255, 255, 255, 0.15); color: #ccc; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;"><i class="fa-solid fa-eye-slash"></i> Ghi nhận</span>`;
            }

            return `
                <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); ${cardBorder} border-radius: 6px; padding: 8px 12px; margin-bottom: 8px; font-family: sans-serif; display: flex; flex-direction: column; gap: 4px; text-align: left;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: bold; font-size: 0.85rem; color: #fff; display: flex; align-items: center; gap: 6px;">
                            <i class="${logTypeIcon}"></i> ${sig.log_type}
                        </span>
                        ${statusBadge}
                    </div>
                    ${detailsHtml}
                    <div style="font-size: 0.75rem; opacity: 0.5; display: flex; justify-content: space-between; align-items: center;">
                        <span><i class="fa-regular fa-clock"></i> ${sig.timestamp.substring(11, 19)}</span>
                        <span style="font-size: 0.7rem; color: #a0a0ff;">KQ: ${sig.reason}</span>
                    </div>
                </div>
            `;
        }).join("");
    }

    // Gắn sự kiện click Trình Mô Phỏng B6
    if (btnSimulateB6) {
        btnSimulateB6.addEventListener("click", async () => {
            btnSimulateB6.disabled = true;
            const originalText = btnSimulateB6.innerHTML;
            btnSimulateB6.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang bắn dữ liệu sang B7...`;

            const randSuffix = Math.floor(Math.random() * 1000);
            const demoPayload = {
                from: new Date(Date.now() - 600000).toISOString(),
                to: new Date().toISOString(),
                data: [
                    {
                        log_type: "ACCESS",
                        timestamp: new Date(Date.now() - 300000).toISOString(),
                        details: {
                            uid: `04:A1:B2:${Math.floor(10 + Math.random() * 89)}`,
                            student_id: `SV${String(100 + randSuffix).substring(1)}`,
                            class_name: "SE1501",
                            gate_id: "GATE-A",
                            action: "GRANTED"
                        }
                    },
                    {
                        log_type: "ACCESS",
                        timestamp: new Date(Date.now() - 150000).toISOString(),
                        details: {
                            uid: `ff:ee:dd:${Math.floor(10 + Math.random() * 89)}`,
                            student_id: `SV${String(500 + randSuffix).substring(1)}`,
                            class_name: "IT3022",
                            gate_id: "GATE-C",
                            action: "DENIED"
                        }
                    },
                    {
                        log_type: "FIRE_ALARM",
                        timestamp: new Date().toISOString(),
                        details: {
                            device_id: `esp32-lab-${randSuffix}`,
                            location: `Lab Room ${randSuffix}`,
                            temperature: parseFloat((45 + Math.random() * 15).toFixed(1)),
                            action: "EVACUATION_TRIGGERED"
                        }
                    }
                ]
            };

            try {
                const response = await fetch(`${API_BASE}/analytics/export`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Source-Service": "core-business-b6"
                    },
                    body: JSON.stringify(demoPayload)
                });

                if (!response.ok) throw new Error("Mô phỏng B6 thất bại");
                
                showToast("Tín hiệu B6 đã gửi thành công!", "success");
                await fetchInboundSignals();
                await fetchLogs();
            } catch (err) {
                showToast(err.message, "error");
            } finally {
                btnSimulateB6.disabled = false;
                btnSimulateB6.innerHTML = originalText;
            }
        });
    }


    // 4. Fetch Logs and Update Metrics
    let cachedLogs = [];

    async function fetchLogs() {
        try {
            const response = await fetch(`${API_BASE}/api/v1/alerts/logs?limit=50`);
            if (!response.ok) throw new Error("Không thể tải nhật ký");

            const logs = await response.json();
            cachedLogs = logs;
            renderLogs();
            updateMetrics(logs);
        } catch (error) {
            console.error("Lỗi đồng bộ logs:", error);
        }
    }

    function updateMetrics(logs) {
        let total = logs.length;
        let success = 0;
        let dedup = 0;
        let retrySum = 0;

        logs.forEach(log => {
            if (log.sent) success++;
            if (log.status === "duplicate_ignored") dedup++;
            if (log.retry_count) retrySum += log.retry_count;
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
            return;
        }

        logsFeedContainer.innerHTML = filtered.map(log => {
            let channelIcon = "fa-solid fa-bell";
            if (log.channel === "telegram") channelIcon = "fa-brands fa-telegram text-blue";
            if (log.channel === "discord") channelIcon = "fa-brands fa-discord text-purple";
            if (log.channel === "email") channelIcon = "fa-solid fa-envelope text-red";
            if (log.channel === "sms") channelIcon = "fa-solid fa-comment-sms";
            if (log.channel === "zalo") channelIcon = "fa-solid fa-square-phone";

            const retryHtml = log.retry_count > 0 ? `
                <span class="retry-indicator">
                    <i class="fa-solid fa-arrows-rotate fa-spin"></i> Retry: ${log.retry_count}
                </span>
            ` : "";

            return `
                <div class="log-item" data-log-id="${log.alert_id}" data-timestamp="${log.timestamp}" data-channel="${log.channel}">
                    <div class="log-header">
                        <div class="log-id-group">
                            <span class="log-id" title="Event ID: ${log.event_id || 'N/A'}">Event: ${(log.event_id || '').substring(0, 8)}...</span>
                            <span class="log-id" title="Alert ID: ${log.alert_id}">Alert: ${log.alert_id.substring(0, 8)}...</span>
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
                        <span class="log-time"><i class="fa-regular fa-clock"></i> ${log.timestamp}</span>
                        <span class="ticket-tag" style="font-family: monospace; font-size: 0.72rem; opacity: 0.6;" title="Ticket ID: ${log.ticket_id}">
                            <i class="fa-solid fa-ticket"></i> Ticket: ${log.ticket_id.substring(0, 8)}...
                        </span>
                        ${retryHtml}
                    </div>
                </div>
            `;

        }).join("");

        // Gắn sự kiện click mở modal xem chi tiết JSON cho từng log card
        document.querySelectorAll(".log-item").forEach(item => {
            item.addEventListener("click", () => {
                const alertId = item.getAttribute("data-log-id");
                const channel = item.getAttribute("data-channel");
                const timestamp = item.getAttribute("data-timestamp");
                const log = cachedLogs.find(l => l.alert_id === alertId && l.channel === channel && l.timestamp === timestamp);
                if (log) {
                    modalJson.innerText = JSON.stringify(log, null, 4);
                    logModal.classList.add("open");
                }
            });
        });
    }

    // Gắn sự kiện lọc dữ liệu tức thì
    searchInput.addEventListener("input", renderLogs);
    filterSeverity.addEventListener("change", renderLogs);
    filterChannel.addEventListener("change", renderLogs);

    // Refresh logs thủ công
    btnRefresh.addEventListener("click", () => {
        showToast("Đang đồng bộ dữ liệu...", "info");
        fetchLogs();
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

    // --- Khởi động ứng dụng ---
    fetchLogs();
    fetchInboundSignals();
    fetchChannelConfigs();

    // Bật Polling đồng bộ logs thời gian thực mỗi 4 giây
    setInterval(() => {
        fetchLogs();
        fetchInboundSignals();
    }, 4000);
});
