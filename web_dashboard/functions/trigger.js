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
        const response = await fetch(
            `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/run_bot.yml/dispatches`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `token ${GITHUB_TOKEN}`,
                    'Accept': 'application/vnd.github.v3+json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ ref: 'main' })
            }
        );

        if (response.status === 204 || response.status === 200) {
            return {
                statusCode: 204,
                body: ""
            };
        } else {
            const errorData = await response.json();
            return {
                statusCode: response.status,
                body: JSON.stringify({ message: errorData.message || response.statusText })
            };
        }
    } catch (error) {
        console.error("Error triggering GitHub Action:", error.message);
        return {
            statusCode: 500,
            body: JSON.stringify({ message: error.message })
        };
    }
};
