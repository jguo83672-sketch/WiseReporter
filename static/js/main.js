/**
 * WiseReporter JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // 自动隐藏提示消息
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.3s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// 工具函数
const Utils = {
    // 格式化日期
    formatDate: function(date) {
        if (!date) return '-';
        const d = new Date(date);
        return d.toLocaleDateString('zh-CN');
    },
    
    // 格式化时间
    formatDateTime: function(date) {
        if (!date) return '-';
        const d = new Date(date);
        return d.toLocaleString('zh-CN');
    },
    
    // 防抖
    debounce: function(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    },
    
    // POST请求
    post: async function(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',  // 确保发送 session cookie
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 100)}`);
        }
        return response.json();
    },
    
    // GET请求
    get: async function(url) {
        const response = await fetch(url, {
            credentials: 'same-origin'  // 确保发送 session cookie
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.substring(0, 100)}`);
        }
        return response.json();
    },
    
    // DELETE请求
    delete: async function(url) {
        const response = await fetch(url, {
            method: 'DELETE'
        });
        return response.json();
    }
};

// 通知提示
const Toast = {
    show: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type}`;
        toast.textContent = message;
        toast.style.position = 'fixed';
        toast.style.top = '80px';
        toast.style.right = '20px';
        toast.style.zIndex = '9999';
        toast.style.minWidth = '200px';
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.transition = 'opacity 0.3s';
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },
    
    success: function(message) {
        this.show(message, 'success');
    },
    
    error: function(message) {
        this.show(message, 'error');
    },
    
    info: function(message) {
        this.show(message, 'info');
    }
};

// API调用封装
const API = {
    // 获取统计数据
    async getStats() {
        return Utils.get('/api/stats/dashboard');
    },
    
    // 采集操作
    async crawlAccount(accountId) {
        return Utils.post(`/api/crawl/account/${accountId}`, {});
    },
    
    async crawlAll() {
        return Utils.post('/api/crawl/all', {});
    },
    
    async crawlAINews() {
        return Utils.post('/api/ai-news/crawl', {});
    },
    
    // 周报操作
    async generateReport(startDate, endDate) {
        return Utils.post('/api/reports/generate', { startDate, endDate });
    },
    
    async publishReport(reportId) {
        return Utils.post(`/api/reports/${reportId}/publish`, {});
    }
};

// 导出全局
window.Utils = Utils;
window.Toast = Toast;
window.API = API;
