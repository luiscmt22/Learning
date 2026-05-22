// Learning Webbook — JS Interop for Blazor MAUI

// ═══ THEME ═══
window.themeInterop = {
    setTheme: function (theme) {
        document.documentElement.setAttribute('data-theme', theme);
    },
    getTheme: function () {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    }
};

// ═══ SCROLL ═══
window.scrollInterop = {
    scrollToElement: function (elementId) {
        var el = document.getElementById(elementId);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    },
    scrollToTop: function () {
        var main = document.querySelector('.main-content');
        if (main) main.scrollTop = 0;
    }
};

// ═══ SIDEBAR (mobile) ═══
window.sidebarInterop = {
    toggleSidebar: function () {
        var sidebar = document.getElementById('sidebar');
        if (sidebar) sidebar.classList.toggle('open');
    },
    closeSidebar: function () {
        var sidebar = document.getElementById('sidebar');
        if (sidebar) sidebar.classList.remove('open');
    }
};

// ═══ GLOBAL FUNCTIONS USED BY PRE-RENDERED HTML ═══
// The embedded demos have onclick="toggleEmbed('embed-xxx')" baked into the HTML.
// These must exist as global functions.

function toggleEmbed(id) {
    var w = document.getElementById('wrap-' + id);
    if (!w) return;
    var bar = w.previousElementSibling;
    var icon = bar ? bar.querySelector('.embed-icon') : null;
    if (w.style.display === 'none' || w.style.display === '') {
        w.style.display = 'block';
        if (icon) icon.style.transform = 'rotate(90deg)';
        // Run any deferred scripts inside the embed
        initEmbedScripts(w);
    } else {
        w.style.display = 'none';
        if (icon) icon.style.transform = 'rotate(0deg)';
    }
}

function toggleFD(tid) {
    var el = document.getElementById('fd-' + tid);
    if (!el) return;
    var btn = el.parentElement ? el.parentElement.querySelector('.fd-btn') : null;
    if (el.style.display === 'none' || el.style.display === '') {
        el.style.display = 'block';
        if (btn) btn.innerHTML = '&#x1f4a1; Hide Simple Explanation';
    } else {
        el.style.display = 'none';
        if (btn) btn.innerHTML = '&#x1f4a1; Show Simple Explanation';
    }
}

// Re-initialize scripts in embedded demos after they become visible
var _embedsInitialized = {};
function initEmbedScripts(wrapper) {
    if (!wrapper) return;
    var id = wrapper.id;
    if (_embedsInitialized[id]) return;
    _embedsInitialized[id] = true;

    // Find script tags that were injected as HTML and re-execute them
    var scripts = wrapper.querySelectorAll('script');
    scripts.forEach(function (oldScript) {
        var newScript = document.createElement('script');
        if (oldScript.src) {
            newScript.src = oldScript.src;
        } else {
            newScript.textContent = oldScript.textContent;
        }
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });
}

// ═══ ACTIVATE SCRIPTS IN BLAZOR-RENDERED HTML ═══
// When Blazor injects HTML via MarkupString, <script> tags don't execute.
// This finds them and re-creates them so the browser executes them.
var _activatedContainers = {};
function activateScripts(containerId) {
    if (_activatedContainers[containerId]) return;
    var container = document.getElementById(containerId);
    if (!container) return;
    _activatedContainers[containerId] = true;

    // Don't auto-run scripts inside hidden embed wrappers —
    // those get activated when toggleEmbed() shows them.
    // Only activate scripts that are NOT inside a display:none wrapper.
    var scripts = container.querySelectorAll('script');
    scripts.forEach(function (oldScript) {
        // Skip scripts inside hidden embed wrappers
        var embedWrapper = oldScript.closest('.embed-wrapper');
        if (embedWrapper && (embedWrapper.style.display === 'none' || embedWrapper.style.display === '')) {
            return;
        }
        var newScript = document.createElement('script');
        if (oldScript.src) {
            newScript.src = oldScript.src;
        } else {
            newScript.textContent = oldScript.textContent;
        }
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });
}
