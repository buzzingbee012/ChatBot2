exports.handler = async (event, context) => {
    const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
    const GITHUB_REPO = process.env.GITHUB_REPO;

    if (!GITHUB_TOKEN || !GITHUB_REPO) {
        return {
            statusCode: 500,
            body: JSON.stringify({ message: "Server configuration error: GITHUB_TOKEN or GITHUB_REPO not set." })
        };
    }

    try {
        // 1. Find the latest in_progress run
        const listResponse = await fetch(
            `https://api.github.com/repos/${GITHUB_REPO}/actions/runs?status=in_progress`,
            {
                headers: {
                    'Authorization': `token ${GITHUB_TOKEN}`,
                    'Accept': 'application/vnd.github.v3+json'
                }
            }
        );

        const data = await listResponse.json();
        const runs = data.workflow_runs || [];
        const runToCancel = runs.find(r => r.name.includes("Bot") || r.path.includes("run_bot.yml"));

        if (!runToCancel) {
            return {
                statusCode: 404,
                body: JSON.stringify({ message: "No active runs found to stop." })
            };
        }

        // 2. Cancel the run
        const cancelResponse = await fetch(
            `https://api.github.com/repos/${GITHUB_REPO}/actions/runs/${runToCancel.id}/cancel`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `token ${GITHUB_TOKEN}`,
                    'Accept': 'application/vnd.github.v3+json'
                }
            }
        );

        if (cancelResponse.status === 202) {
            return {
                statusCode: 200,
                body: JSON.stringify({ message: `Successfully stopped run ${runToCancel.id}` })
            };
        } else {
            return {
                statusCode: cancelResponse.status,
                body: JSON.stringify({ message: "Failed to stop bot." })
            };
        }
    } catch (error) {
        console.error("Error stopping GitHub Action:", error.message);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: error.message })
        };
    }
};
