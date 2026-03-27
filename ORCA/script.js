// Artisan Studio | Studio Logic | 2026

document.addEventListener('DOMContentLoaded', () => {
    console.log('Studio Environment Loaded.');

    // Lucide Icons initialization
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // Section Switching (Tabs)
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.content-section');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const targetScroll = window.scrollY; // Preserve scroll position for UX or reset
            e.preventDefault();
            
            const sectionId = link.getAttribute('data-section');
            if (!sectionId) return;

            // Update Tab states
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            // Switch Sections
            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === sectionId) {
                    section.classList.add('active');
                }
            });

            // Re-run icons in case new ones were added dynamically
            lucide.createIcons();
            
            console.log(`Artisan | Switched to: ${sectionId}`);
        });
    });

    // Ambient Hover Effects for Cards
    const cards = document.querySelectorAll('.dish-card, .stat-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.borderColor = 'var(--accent-gold)';
        });
        card.addEventListener('mouseleave', () => {
            card.style.borderColor = 'var(--border-warm)';
        });
    });
});
