// Documentation JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize documentation features
    initTableOfContents();
    initSmoothScrolling();
    initCodeCopyButtons();
    initSearchFunctionality();
    initActiveNavigation();
});

// Generate table of contents automatically
function initTableOfContents() {
    const toc = document.querySelector('.toc-list');
    const content = document.querySelector('.docs-content');
    
    if (!toc || !content) return;
    
    const headings = content.querySelectorAll('h2, h3');
    
    headings.forEach((heading, index) => {
        // Create ID if it doesn't exist
        if (!heading.id) {
            heading.id = heading.textContent.toLowerCase()
                .replace(/[^\w\s-]/g, '')
                .replace(/\s+/g, '-');
        }
        
        // Create TOC item
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = `#${heading.id}`;
        a.textContent = heading.textContent;
        a.className = heading.tagName.toLowerCase() === 'h3' ? 'sub-item' : '';
        
        li.appendChild(a);
        toc.appendChild(li);
    });
}

// Smooth scrolling for anchor links
function initSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                
                // Update active TOC item
                updateActiveTocItem(this.getAttribute('href'));
            }
        });
    });
}

// Add copy buttons to code blocks
function initCodeCopyButtons() {
    const codeBlocks = document.querySelectorAll('pre code');
    
    codeBlocks.forEach(codeBlock => {
        const pre = codeBlock.parentElement;
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copy code';
        
        button.addEventListener('click', () => {
            navigator.clipboard.writeText(codeBlock.textContent).then(() => {
                button.innerHTML = '<i class="fas fa-check"></i>';
                button.style.color = 'var(--success-color)';
                
                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                    button.style.color = '';
                }, 2000);
            });
        });
        
        pre.style.position = 'relative';
        pre.appendChild(button);
    });
}

// Search functionality (basic implementation)
function initSearchFunctionality() {
    const searchInput = document.querySelector('.docs-search');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', function(e) {
        const query = e.target.value.toLowerCase();
        const sections = document.querySelectorAll('.docs-content h2, .docs-content h3, .docs-content p');
        
        sections.forEach(section => {
            const text = section.textContent.toLowerCase();
            const parent = section.closest('section') || section;
            
            if (text.includes(query) || query === '') {
                parent.style.display = '';
            } else {
                parent.style.display = 'none';
            }
        });
    });
}

// Update active navigation items
function initActiveNavigation() {
    const navLinks = document.querySelectorAll('.docs-nav a, .toc-list a');
    const sections = document.querySelectorAll('.docs-content h2, .docs-content h3');
    
    // Intersection Observer for automatic active state
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                updateActiveNavItem(`#${id}`);
            }
        });
    }, {
        rootMargin: '-20% 0px -80% 0px'
    });
    
    sections.forEach(section => {
        if (section.id) {
            observer.observe(section);
        }
    });
}

// Update active TOC item
function updateActiveTocItem(href) {
    document.querySelectorAll('.toc-list a').forEach(link => {
        link.classList.remove('active');
    });
    
    const activeLink = document.querySelector(`.toc-list a[href="${href}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}

// Update active navigation item
function updateActiveNavItem(href) {
    document.querySelectorAll('.docs-nav a, .toc-list a').forEach(link => {
        link.classList.remove('active');
    });
    
    const activeLink = document.querySelector(`.docs-nav a[href="${href}"], .toc-list a[href="${href}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}

// Mobile navigation toggle
function toggleMobileNav() {
    const sidebar = document.querySelector('.docs-sidebar');
    if (sidebar) {
        sidebar.classList.toggle('mobile-open');
    }
}

// Add mobile navigation button if needed
if (window.innerWidth <= 768) {
    const mobileNavButton = document.createElement('button');
    mobileNavButton.className = 'mobile-nav-toggle';
    mobileNavButton.innerHTML = '<i class="fas fa-bars"></i>';
    mobileNavButton.addEventListener('click', toggleMobileNav);
    
    const docsLayout = document.querySelector('.docs-layout');
    if (docsLayout) {
        docsLayout.insertBefore(mobileNavButton, docsLayout.firstChild);
    }
}

// Add CSS for copy buttons and mobile navigation
const style = document.createElement('style');
style.textContent = `
    .copy-button {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: rgba(255, 255, 255, 0.1);
        border: none;
        color: white;
        padding: 0.5rem;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }
    
    .copy-button:hover {
        background: rgba(255, 255, 255, 0.2);
    }
    
    .mobile-nav-toggle {
        display: none;
        background: var(--primary-color);
        color: white;
        border: none;
        padding: 0.75rem;
        border-radius: 4px;
        margin-bottom: 1rem;
        cursor: pointer;
    }
    
    @media (max-width: 768px) {
        .mobile-nav-toggle {
            display: block;
        }
        
        .docs-sidebar {
            display: none;
        }
        
        .docs-sidebar.mobile-open {
            display: block;
        }
    }
    
    .toc-list .sub-item {
        margin-left: 1rem;
        font-size: 0.85rem;
    }
`;
document.head.appendChild(style);
