/**
 * 回测系统前端 JavaScript
 */

let chartInstance = null;
let currentData = null;

// 格式化数字
function formatNumber(num) {
    if (num === null || num === undefined) return "N/A";
    return Number(num).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

// 显示/隐藏元素
function showElement(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
}

function hideElement(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

// 显示结果
function displayResult(data) {
    currentData = data;

    // 更新统计
    document.getElementById('stat-trades').textContent = data.total_trades;
    document.getElementById('stat-investment').textContent = formatNumber(data.total_investment);
    document.getElementById('stat-value').textContent = formatNumber(data.final_value);

    const returnEl = document.getElementById('stat-return');
    returnEl.textContent = (data.return_rate || 0).toFixed(2) + '%';
    returnEl.className = 'stat-value ' + (data.return_rate > 0 ? 'positive' : 'negative');

    document.getElementById('stat-volatility').textContent = ((data.volatility || 0) * 100).toFixed(2) + '%';
    document.getElementById('stat-sharpe').textContent = (data.sharpe_ratio || 0).toFixed(4);

    // 显示结果区域
    showElement('results-section');

    // 渲染买入记录
    const recordsContainer = document.getElementById('records-container');
    const recordsBody = document.getElementById('records-body');
    if (data.buy_records && data.buy_records.length > 0) {
        recordsContainer.style.display = '';
        recordsBody.innerHTML = data.buy_records.map(r => `
            <tr>
                <td>${r.time}</td>
                <td>${(r.price || 0).toFixed(2)}</td>
                <td>${r.volume}</td>
                <td>${formatNumber(r.cost)}</td>
                <td>${r.rsi ? 'RSI:' + r.rsi : ''} ${r.bias ? ' Bias:' + r.bias : ''}</td>
            </tr>
        `).join('');
    } else {
        recordsContainer.style.display = 'none';
    }

    // 渲染图表
    renderChart(data);
}

// 渲染图表
function renderChart(data) {
    const canvas = document.getElementById('price-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const prices = data.prices || [];
    const times = data.times || [];
    const buyRecords = data.buy_records || [];

    // 销毁旧图表
    if (chartInstance) {
        chartInstance.destroy();
    }

    // 获取买入点索引和价格
    const buyPointData = [];
    buyRecords.forEach(r => {
        const idx = times.indexOf(r.time);
        if (idx >= 0) {
            buyPointData.push({ x: r.time, y: prices[idx] });
        }
    });

    const datasets = [
        {
            label: '价格',
            data: prices.map((p, i) => ({ x: times[i], y: p })),
            borderColor: '#1890ff',
            backgroundColor: 'rgba(24, 144, 255, 0.1)',
            fill: true,
            tension: 0.1,
            pointRadius: 2,
            showLine: true,
        }
    ];

    // 添加买入点
    if (buyPointData.length > 0) {
        datasets.push({
            label: '买入点',
            data: buyPointData,
            borderColor: '#ff4d4f',
            backgroundColor: '#ff4d4f',
            pointRadius: 6,
            pointHoverRadius: 8,
            showLine: false,
            type: 'scatter',
        });
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                },
            },
            scales: {
                x: {
                    display: true,
                    ticks: {
                        maxTicksLimit: 10,
                    },
                },
                y: {
                    display: true,
                },
            },
        },
    });
}

// 运行回测
async function runBacktest() {
    const strategy = document.getElementById('strategy').value;
    const stock = document.getElementById('stock').value;
    const duration = document.getElementById('duration').value;

    hideElement('error-section');
    hideElement('results-section');
    showElement('loading');

    try {
        const response = await fetch('/api/backtest', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                strategy: strategy,
                stock_code: stock,
                duration: duration,
            }),
        });

        const result = await response.json();

        hideElement('loading');

        if (!result.success) {
            showElement('error-section');
            document.getElementById('error-message').textContent = result.error || '回测失败';
            return;
        }

        displayResult(result.data);
    } catch (e) {
        hideElement('loading');
        showElement('error-section');
        document.getElementById('error-message').textContent = e.message;
    }
}

// 加载已有数据
async function loadData() {
    const strategy = document.getElementById('strategy').value;
    const stock = document.getElementById('stock').value;

    try {
        const response = await fetch(`/api/data/${strategy}/${stock}`);

        if (!response.ok) {
            // 数据不存在，显示提示
            return;
        }

        const data = await response.json();
        displayResult(data);
    } catch (e) {
        // 忽略加载错误
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 绑定按钮事件
    document.getElementById('run-backtest').addEventListener('click', runBacktest);
    document.getElementById('generate-data').addEventListener('click', runBacktest);

    // 回车触发
    document.getElementById('stock').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            runBacktest();
        }
    });

    // 尝试加载默认数据
    loadData();

    // 加载参数优化结果
    loadParamOptimization();
});

// 加载参数优化结果
async function loadParamOptimization() {
    try {
        // 加载当前配置
        const configRes = await fetch('/api/config');
        if (configRes.ok) {
            const config = await configRes.json();
            document.getElementById('current-config').textContent = JSON.stringify(config.params, null, 2);
        }

        // 加载优化结果
        const res = await fetch('/api/param_optimization');
        if (!res.ok) return;

        const data = await res.json();
        const grid = document.getElementById('best-params-grid');

        // ETF 名称映射
        const etfNames = {
            "563020.SH": "红利低波ETF",
            "520990.SH": "港股央企红利ETF",
            "159545.SZ": "恒生红利低波ETF"
        };

        grid.innerHTML = Object.entries(data).map(([code, results]) => {
            const best = results[0];
            return `
                <div class="etf-result">
                    <h4>${etfNames[code] || code} (${code})</h4>
                    <div class="result-stats">
                        <span class="positive">收益率: ${best.return_rate.toFixed(2)}%</span>
                        <span>交易次数: ${best.total_trades}</span>
                        <span>夏普比率: ${best.sharpe_ratio.toFixed(4)}</span>
                    </div>
                    <div class="result-params">
                        <div>RSI: overbought=${best.params.rsi_overbought}, oversold=${best.params.rsi_oversold}, additional=${best.params.rsi_additional}</div>
                        <div>Bias: upper=${best.params.bias_upper}, lower=${best.params.bias_lower}, additional=${best.params.bias_additional}</div>
                    </div>
                </div>
            `;
        }).join('');

        showElement('param-results-section');
    } catch (e) {
        console.error('加载参数优化结果失败:', e);
    }
}