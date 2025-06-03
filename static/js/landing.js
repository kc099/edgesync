document.addEventListener('DOMContentLoaded', () => {
    // Smooth scrolling for navigation links
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

    // Navbar scroll effect
    const navbar = document.querySelector('.navbar');
    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        if (currentScroll <= 0) {
            navbar.classList.remove('scroll-up');
            return;
        }

        if (currentScroll > lastScroll && !navbar.classList.contains('scroll-down')) {
            // Scroll Down
            navbar.classList.remove('scroll-up');
            navbar.classList.add('scroll-down');
        } else if (currentScroll < lastScroll && navbar.classList.contains('scroll-down')) {
            // Scroll Up
            navbar.classList.remove('scroll-down');
            navbar.classList.add('scroll-up');
        }
        lastScroll = currentScroll;
    });

    // Intersection Observer for fade-in animations
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

    // Feature cards hover effect
    const featureCards = document.querySelectorAll('.feature-card');
    featureCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-10px)';
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
        });
    });

    // Mobile menu toggle (if needed)
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

    // Initialize mobile menu if screen width is small
    if (window.innerWidth <= 768) {
        createMobileMenu();
    }

    // Add CSS classes for animations
    const style = document.createElement('style');
    style.textContent = `
        .fade-out {
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.6s ease-out, transform 0.6s ease-out;
        }
        
        .fade-in {
            opacity: 1;
            transform: translateY(0);
        }

        .navbar.scroll-down {
            transform: translateY(-100%);
            transition: transform 0.3s ease-in-out;
        }

        .navbar.scroll-up {
            transform: translateY(0);
            transition: transform 0.3s ease-in-out;
        }

        @media (max-width: 768px) {
            .nav-links {
                position: fixed;
                top: 70px;
                left: 0;
                right: 0;
                background: white;
                padding: 1rem;
                flex-direction: column;
                align-items: center;
                transform: translateY(-100%);
                transition: transform 0.3s ease-in-out;
                box-shadow: var(--shadow-md);
            }

            .nav-links.active {
                transform: translateY(0);
            }

            .mobile-menu-button {
                display: block;
                background: none;
                border: none;
                font-size: 1.5rem;
                color: var(--text-color);
                cursor: pointer;
                padding: 0.5rem;
            }

            .mobile-menu-button.active i:before {
                content: "\\f00d";
            }
        }
    `;
    document.head.appendChild(style);

    // Parallax effect for hero section
    const hero = document.querySelector('.hero');
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        if (hero) {
            hero.style.backgroundPositionY = `${scrolled * 0.5}px`;
        }
    });

    // Add loading animation for images
    document.querySelectorAll('img').forEach(img => {
        img.addEventListener('load', () => {
            img.classList.add('loaded');
        });
    });

    // Initialize landing page specific features
    initializeFeatureCards();
    initializeSolutionCards();
    initializeBenefitsAnimation();
});

// Feature Cards Animation
function initializeFeatureCards() {
    const cards = document.querySelectorAll('.feature-card');
    
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-10px)';
            card.style.boxShadow = 'var(--shadow-lg)';
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = 'var(--shadow-sm)';
        });
    });
}

// Solution Cards Animation
function initializeSolutionCards() {
    const cards = document.querySelectorAll('.solution-card');
    
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-10px)';
            card.style.boxShadow = 'var(--shadow-md)';
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = 'var(--shadow-sm)';
        });
    });
}

// Benefits Section Animation
function initializeBenefitsAnimation() {
    const benefits = document.querySelectorAll('.benefit-item');
    
    benefits.forEach(benefit => {
        benefit.addEventListener('mouseenter', () => {
            benefit.style.background = 'rgba(255, 255, 255, 0.2)';
            benefit.style.transform = 'scale(1.05)';
        });

        benefit.addEventListener('mouseleave', () => {
            benefit.style.background = 'rgba(255, 255, 255, 0.1)';
            benefit.style.transform = 'scale(1)';
        });
    });
}

// Platform Visual Animation
const platformVisual = document.querySelector('.platform-visual');
if (platformVisual) {
    let isAnimating = true;
    
    function animatePlatform() {
        if (!isAnimating) return;
        
        platformVisual.style.animation = 'float 6s ease-in-out infinite';
        requestAnimationFrame(animatePlatform);
    }
    
    // Start animation
    animatePlatform();
    
    // Pause animation when not in viewport
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            isAnimating = entry.isIntersecting;
            if (!isAnimating) {
                platformVisual.style.animation = 'none';
            } else {
                platformVisual.style.animation = 'float 6s ease-in-out infinite';
            }
        });
    }, { threshold: 0.1 });
    
    observer.observe(platformVisual);
} 