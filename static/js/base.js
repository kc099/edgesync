// Base JavaScript functionality
document.addEventListener('DOMContentLoaded', () => {
    // Initialize the EdgeSync global object
    window.EdgeSync.init();

    // Common navigation functionality
    const initNavigation = () => {
        const navbar = document.querySelector('.navbar');
        let lastScroll = 0;

        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;

            if (currentScroll <= 0) {
                navbar.classList.remove('scroll-up');
                return;
            }

            if (currentScroll > lastScroll && !navbar.classList.contains('scroll-down')) {
                navbar.classList.remove('scroll-up');
                navbar.classList.add('scroll-down');
            } else if (currentScroll < lastScroll && navbar.classList.contains('scroll-down')) {
                navbar.classList.remove('scroll-down');
                navbar.classList.add('scroll-up');
            }
            lastScroll = currentScroll;
        });

        // Mobile menu functionality
        const createMobileMenu = () => {
            const nav = document.querySelector('.nav-links');
            const menuButton = document.createElement('button');
            menuButton.classList.add('mobile-menu-button');
            menuButton.innerHTML = '<i class="fas fa-bars"></i>';
            
            const navContainer = document.querySelector('.nav-container');
            navContainer.insertBefore(menuButton, nav);

            menuButton.addEventListener('click', () => {
                nav.classList.toggle('active');
                menuButton.classList.toggle('active');
            });
        };

        if (window.innerWidth <= 768) {
            createMobileMenu();
        }
    };

    // Common animation functionality
    const initAnimations = () => {
        const observerOptions = {
            root: null,
            rootMargin: '0px',
            threshold: 0.1
        };

        const observer = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in');
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        // Observe all sections
        document.querySelectorAll('section').forEach(section => {
            section.classList.add('fade-out');
            observer.observe(section);
        });
    };

    // Smooth scrolling for anchor links
    const initSmoothScroll = () => {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    };

    // Initialize all common functionality
    initNavigation();
    initAnimations();
    initSmoothScroll();

    // Add common utility functions to EdgeSync global object
    window.EdgeSync.utils = {
        ...window.EdgeSync.utils,
        debounce: (func, wait) => {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        throttle: (func, limit) => {
            let inThrottle;
            return function executedFunction(...args) {
                if (!inThrottle) {
                    func(...args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        }
    };
}); 