const THEME_STORAGE_KEY = 'theme';

function getPreferredTheme() {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme;

    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function updateThemeIcon(theme) {
    const mainIcon = document.getElementById('theme-icon');
    if (mainIcon) {
        mainIcon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    }

    // Standalone pages use a two-icon button rather than #theme-icon.
    const lightIcon = document.getElementById('themeIconLight');
    const darkIcon = document.getElementById('themeIconDark');
    if (lightIcon) lightIcon.classList.toggle('d-none', theme !== 'dark');
    if (darkIcon) darkIcon.classList.toggle('d-none', theme === 'dark');
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    updateThemeIcon(theme);
}

// Run immediately in <head> to avoid a flash of the incorrect theme.
applyTheme(getPreferredTheme());

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    applyTheme(newTheme);
}

document.addEventListener('DOMContentLoaded', () => applyTheme(getPreferredTheme()));

// Keep an already-open page in sync when the preference changes in another tab.
window.addEventListener('storage', (event) => {
    if (event.key === THEME_STORAGE_KEY && (event.newValue === 'light' || event.newValue === 'dark')) {
        applyTheme(event.newValue);
    }
});
