let sentimentChart;
let keywordChart;

const sourceEl = document.getElementById("source");
const queryLabel = document.getElementById("queryLabel");
const queryInput = document.getElementById("query");
const manualLabel = document.getElementById("manualLabel");
const manualText = document.getElementById("manualText");
const statusMsg = document.getElementById("statusMsg");
const resultsSection = document.getElementById("resultsSection");

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function toggleInputVisibility() {
    const source = sourceEl.value;
    if (source === "manual") {
        manualLabel.classList.remove("hidden");
        queryLabel.classList.add("hidden");
        queryInput.value = "";
    } else if (source === "csv") {
        manualLabel.classList.add("hidden");
        queryLabel.classList.add("hidden");
        queryInput.value = "";
        manualText.value = "";
    } else {
        manualLabel.classList.add("hidden");
        queryLabel.classList.remove("hidden");
        manualText.value = "";
    }
}

function updateAnalytics(analytics) {
    document.getElementById("totalReviews").textContent = analytics.total_reviews;
    document.getElementById("positivePct").textContent = `${analytics.positive_percentage}%`;
    document.getElementById("negativePct").textContent = `${analytics.negative_percentage}%`;
    document.getElementById("satisfactionLabel").textContent = analytics.overall_customer_satisfaction;
    document.getElementById("satisfactionScore").textContent = `Score: ${analytics.satisfaction_score}`;

    const keywordList = document.getElementById("keywordList");
    keywordList.innerHTML = "";
    analytics.most_common_keywords.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = `${item.keyword} (${item.count})`;
        keywordList.appendChild(li);
    });
}

function renderReviewTable(reviews) {
    const container = document.getElementById("reviewTable");
    if (!reviews.length) {
        container.innerHTML = "<p>No reviews returned.</p>";
        return;
    }

    const rows = reviews.map((r, idx) => {
        const sentimentClass = r.sentiment.toLowerCase();
        return `
            <tr>
                <td>${idx + 1}</td>
                <td><span class="badge ${sentimentClass}">${escapeHtml(r.sentiment)}</span></td>
                <td>${escapeHtml(r.text)}</td>
                <td>${escapeHtml(r.platform || "")}</td>
            </tr>
        `;
    }).join("");

    container.innerHTML = `
        <table class="review-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Sentiment</th>
                    <th>Review</th>
                    <th>Source</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

function renderCharts(chartData) {
    const sentimentCtx = document.getElementById("sentimentChart").getContext("2d");
    const keywordCtx = document.getElementById("keywordChart").getContext("2d");

    if (sentimentChart) sentimentChart.destroy();
    if (keywordChart) keywordChart.destroy();

    sentimentChart = new Chart(sentimentCtx, {
        type: "pie",
        data: chartData.sentiment,
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: "bottom"
                }
            }
        }
    });

    keywordChart = new Chart(keywordCtx, {
        type: "bar",
        data: chartData.keywords,
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 }
                }
            }
        }
    });
}

sourceEl.addEventListener("change", toggleInputVisibility);
toggleInputVisibility();

document.getElementById("analyzeForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
        source: sourceEl.value,
        query: queryInput.value.trim(),
        manual_text: manualText.value,
        max_reviews: Number(document.getElementById("maxReviews").value || 50)
    };

    statusMsg.textContent = "Analyzing reviews...";

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Analysis failed");
        }

        updateAnalytics(data.analytics);
        renderCharts(data.charts);
        renderReviewTable(data.reviews);

        resultsSection.classList.remove("hidden");
        statusMsg.textContent = `Done. Processed ${data.analytics.total_reviews} reviews from ${data.source}.`;
    } catch (err) {
        statusMsg.textContent = `Error: ${err.message}`;
        resultsSection.classList.add("hidden");
    }
});
