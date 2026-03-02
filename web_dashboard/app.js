// Initialize Firebase
if (typeof firebaseConfig === 'undefined' || firebaseConfig.apiKey === "YOUR_API_KEY") {
    console.error("Firebase Config missing! Please update config.js");
    document.getElementById('log-container').innerHTML = '<div class="log-entry" style="color: #ff7b72;">Error: Config not set. Please update config.js</div>';
} else {
    firebase.initializeApp(firebaseConfig);
    const db = firebase.database();

    // Elements
    const elTodayInteractions = document.getElementById('today-interactions');
    const elTodayTokens = document.getElementById('today-tokens');
    const elTotalInteractions = document.getElementById('total-interactions');
    const elTotalTokens = document.getElementById('total-tokens');
    const elTodayErrors = document.getElementById('today-errors');
    const elLogContainer = document.getElementById('log-container');
    const elHistoryTableBody = document.getElementById('history-table-body');

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

    // Listen to Stats
    console.log("Listening for stats...");
    db.ref('stats').on('value', (snapshot) => {
        const data = snapshot.val();
        if (!data) return;

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
        // We use the already processed `dates` array but reverse it only for display
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
    });
}

// GitHub Action Controls
const elGhToken = document.getElementById('gh-token');
const elGhRepo = document.getElementById('gh-repo');
const elBtnStart = document.getElementById('btn-start');
const elBtnStop = document.getElementById('btn-stop');
const elControlStatus = document.getElementById('control-status');

// Load saved credentials
if (localStorage.getItem('gh-token')) elGhToken.value = localStorage.getItem('gh-token');
if (localStorage.getItem('gh-repo')) elGhRepo.value = localStorage.getItem('gh-repo');

function setStatus(msg, color = 'var(--text-secondary)') {
    elControlStatus.innerText = msg;
    elControlStatus.style.color = color;
}

async function triggerGitHubAction() {
    const token = elGhToken.value;
    const repo = elGhRepo.value;

    if (!token || !repo) {
        alert("Please enter GitHub Token and Repository!");
        return;
    }

    // Save to local storage
    localStorage.setItem('gh-token', token);
    localStorage.setItem('gh-repo', repo);

    elBtnStart.disabled = true;
    setStatus("Triggering...", "var(--accent)");

    try {
        const response = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/run_bot.yml/dispatches`, {
            method: 'POST',
            headers: {
                'Authorization': `token ${token}`,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ref: 'main' })
        });

        if (response.status === 204) {
            setStatus("Bot Start Secretly Requested!", "#3fb950");
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
    const token = elGhToken.value;
    const repo = elGhRepo.value;

    if (!token || !repo) {
        alert("Please enter GitHub Token and Repository!");
        return;
    }

    elBtnStop.disabled = true;
    setStatus("Finding active runs...", "var(--accent)");

    try {
        // 1. Find the latest in_progress run
        const listResponse = await fetch(`https://api.github.com/repos/${repo}/actions/runs?status=in_progress`, {
            headers: {
                'Authorization': `token ${token}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        const data = await listResponse.json();
        const runs = data.workflow_runs || [];

        // Filter for our run_bot.yml workflow (or just use the first match)
        const runToCancel = runs.find(r => r.name.includes("Bot") || r.path.includes("run_bot.yml"));

        if (!runToCancel) {
            setStatus("No active runs found to stop.", "#f85149");
            setTimeout(() => setStatus("Ready"), 3000);
            return;
        }

        setStatus(`Stopping run ${runToCancel.id}...`, "#f85149");

        // 2. Cancel the run
        const cancelResponse = await fetch(`https://api.github.com/repos/${repo}/actions/runs/${runToCancel.id}/cancel`, {
            method: 'POST',
            headers: {
                'Authorization': `token ${token}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (cancelResponse.status === 202) {
            setStatus("Bot Stop Requested successfully!", "#3fb950");
            setTimeout(() => setStatus("Ready"), 5000);
        } else {
            setStatus("Failed to stop bot.", "#f85149");
        }
    } catch (e) {
        setStatus(`Error: ${e.message}`, "#f85149");
    } finally {
        elBtnStop.disabled = false;
    }
}

