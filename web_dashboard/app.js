// Initialize Supabase
if (typeof supabaseUrl === 'undefined' || supabaseUrl === "YOUR_SUPABASE_URL") {
    console.error("Supabase Config missing! Please update config.js");
    document.getElementById('log-container').innerHTML = '<div class="log-entry" style="color: #ff7b72;">Error: Config not set. Please update config.js</div>';
} else {
    // Create Supabase Client
    window.supabaseClient = supabase.createClient(supabaseUrl, supabaseAnonKey);

    // Elements
    const elTodayInteractions = document.getElementById('today-interactions');
    const elTodayTokens = document.getElementById('today-tokens');
    const elTotalInteractions = document.getElementById('total-interactions');
    const elTotalTokens = document.getElementById('total-tokens');
    const elTodayErrors = document.getElementById('today-errors');
    const elLogContainer = document.getElementById('log-container');
    const elHistoryTableBody = document.getElementById('history-table-body');
    const elExhaustedTableBody = document.getElementById('exhausted-table-body');

    // Chart
    const ctx = document.getElementById('activityChart').getContext('2d');
    let activityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Daily Interactions',
                data: [],
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#8b949e' } }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(240, 246, 252, 0.1)' },
                    ticks: { color: '#8b949e' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#8b949e' }
                }
            }
        }
    });

    async function fetchStats() {
        console.log("Fetching stats from Supabase...");
        const { data: appData, error } = await supabaseClient
            .from('app_data')
            .select('value')
            .eq('key', 'stats')
            .single();

        if (error) {
            console.error("Error fetching stats:", error);
            return;
        }

        if (appData && appData.value) {
            const data = appData.value;
            console.log("Data received:", data);

            // Process Data
            const dates = Object.keys(data).sort(); // Sort dates
            const today = new Date().toISOString().split('T')[0];

            let total = 0;
            let totalTokens = 0;
            const chartLabels = [];
            const chartData = [];
            let todayStats = { interactions: 0, tokens: 0, errors: [] };

            dates.forEach(date => {
                let stats = data[date];

                // Handle legacy format (int)
                let interactions = 0;
                let tokens = 0;
                let errors = [];

                if (typeof stats === 'number') {
                    interactions = stats;
                } else {
                    interactions = stats.interactions || 0;
                    tokens = stats.tokens || 0;
                    errors = stats.errors || [];
                }

                total += interactions;
                totalTokens += tokens;
                chartLabels.push(date);
                chartData.push(interactions);

                if (date === today) {
                    todayStats = { interactions, tokens, errors };
                }
            });

            // Populate History Table (Reverse Chronological)
            const reversedDates = [...dates].reverse();
            elHistoryTableBody.innerHTML = reversedDates.map(date => {
                let stats = data[date];
                let interactions = (typeof stats === 'number') ? stats : (stats.interactions || 0);
                let tokens = (typeof stats === 'number') ? 0 : (stats.tokens || 0);

                return `
                    <tr style="border-bottom: 1px solid rgba(240, 246, 252, 0.05);">
                        <td style="padding: 15px;">${date}</td>
                        <td style="padding: 15px; font-weight: 500;">${interactions}</td>
                        <td style="padding: 15px; color: var(--text-secondary);">${tokens}</td>
                    </tr>
                `;
            }).join('');

            // Update UI
            elTodayInteractions.innerText = todayStats.interactions;
            elTodayTokens.innerText = todayStats.tokens;
            elTotalInteractions.innerText = total;
            elTotalTokens.innerText = totalTokens;
            elTodayErrors.innerText = todayStats.errors.length;

            // Update Logs
            if (todayStats.errors.length > 0) {
                elLogContainer.innerHTML = todayStats.errors.map(e => `
                    <div class="log-entry">
                        <span style="color: #ff7b72;">${e.time}</span>
                        <span>${e.message}</span>
                    </div>
                `).join('');
            } else {
                elLogContainer.innerHTML = '<div class="log-entry" style="justify-content: center; color: var(--text-secondary);">No errors today. System healthy.</div>';
            }

            // Update Chart
            activityChart.data.labels = chartLabels;
            activityChart.data.datasets[0].data = chartData;
            activityChart.update();
        }
    }

    // Modal Logic
    const chatModal = document.getElementById("chatModal");
    const closeModal = document.getElementById("closeModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalChatContent = document.getElementById("modalChatContent");

    closeModal.onclick = function () { chatModal.style.display = "none"; }
    window.onclick = function (event) { if (event.target == chatModal) chatModal.style.display = "none"; }

    window.openChatModal = function (userName, historyJson) {
        modalTitle.innerText = `Chat History for ${userName}`;

        let historyArr = [];
        try {
            historyArr = JSON.parse(decodeURIComponent(historyJson));
        } catch (e) { console.error(e); }

        modalChatContent.innerHTML = historyArr.map(msg => {
            let bgColor = msg.role === 'assistant' ? 'rgba(88, 166, 255, 0.1)' : 'rgba(255,255,255,0.05)';
            let bColor = msg.role === 'assistant' ? '#58a6ff' : 'var(--card-border)';
            return `
                <div style="margin-bottom: 10px; background: ${bgColor}; padding: 10px; border-radius: 8px; border: 1px solid ${bColor}">
                    <strong style="color: var(--text-secondary);">${msg.role.toUpperCase()}</strong>
                    <div style="margin-top: 5px;">${msg.content}</div>
                </div>
            `;
        }).join('');

        chatModal.style.display = "block";
    }

    async function fetchExhaustedChats() {
        const { data, error } = await supabaseClient
            .from('exhausted_chats')
            .select('*')
            .order('created_at', { ascending: false })
            .limit(50);

        if (error) {
            console.error("Error fetching exhausted chats:", error);
            return;
        }

        if (data) {
            elExhaustedTableBody.innerHTML = data.map(chat => {
                let dateStr = new Date(chat.created_at).toLocaleString();
                let encodedHistory = encodeURIComponent(JSON.stringify(chat.history || []));
                return `
                    <tr style="border-bottom: 1px solid rgba(240, 246, 252, 0.05);">
                        <td style="padding: 15px;">${dateStr}</td>
                        <td style="padding: 15px;">${chat.user_name}</td>
                        <td style="padding: 15px;">${chat.bot_name}</td>
                        <td style="padding: 15px;">
                            <button onclick="openChatModal('${chat.user_name}', '${encodedHistory}')" style="background:#58a6ff; color:#fff; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">View</button>
                        </td>
                    </tr>
                `;
            }).join('');
        }
    }

    // Initial Fetch & Refresh Interval
    fetchStats();
    fetchExhaustedChats();
    setInterval(() => {
        fetchStats();
        fetchExhaustedChats();
    }, 10000); // 10 seconds polling (simulates realtime for simple dashboard)
}

// GitHub Action Controls
const elBtnStart = document.getElementById('btn-start');
const elBtnStop = document.getElementById('btn-stop');
const elControlStatus = document.getElementById('control-status');

function setStatus(msg, color = 'var(--text-secondary)') {
    elControlStatus.innerText = msg;
    elControlStatus.style.color = color;
}

async function triggerGitHubAction() {
    elBtnStart.disabled = true;
    setStatus("Triggering...", "var(--accent)");

    try {
        const response = await fetch('/api/trigger', { method: 'POST' });
        if (response.status === 204 || response.status === 200) {
            setStatus("Bot Start Requested!", "#3fb950");
            setTimeout(() => setStatus("Ready"), 5000);
        } else {
            const errData = await response.json();
            setStatus(`Error: ${errData.message || response.statusText}`, "#f85149");
        }
    } catch (e) {
        setStatus(`Network Error: ${e.message}`, "#f85149");
    } finally {
        elBtnStart.disabled = false;
    }
}

async function stopGitHubAction() {
    elBtnStop.disabled = true;
    setStatus("Stopping...", "var(--accent)");

    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        if (response.ok) {
            const data = await response.json();
            setStatus(data.message || "Bot Stop Requested!", "#3fb950");
            setTimeout(() => setStatus("Ready"), 5000);
        } else {
            const errData = await response.json();
            setStatus(`Error: ${errData.message || response.statusText}`, "#f85149");
        }
    } catch (e) {
        setStatus(`Error: ${e.message}`, "#f85149");
    } finally {
        elBtnStop.disabled = false;
    }
}
