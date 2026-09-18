document.addEventListener('DOMContentLoaded', () => {
    // Smooth scrolling for internal anchor links (leave download/file links alone)
    document.querySelectorAll('nav a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            document.querySelector(targetId).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // Re-initialize Twitter widgets if script is already loaded
    if (window.twttr && window.twttr.widgets) {
        window.twttr.widgets.load();
    }
});
