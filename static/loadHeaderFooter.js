// loadHeaderFooter.js

async function loadComponent(id, file) {
  try {
    const response = await fetch(file);
    const html = await response.text();
    document.getElementById(id).innerHTML = html;

    if (id === "header") {
      initHamburgerToggle();
      highlightActiveNav();
    }

    if (id === "footer") {
      initFooterForm();
    }
  } catch (err) {
    console.error(`Error loading ${file}:`, err);
  }
}

function initHamburgerToggle() {
  const menuToggle = document.querySelector('.menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  const overlay = document.querySelector('.overlay');

  if (!menuToggle || !navLinks || !overlay) return;

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    navLinks.classList.toggle('active');
    overlay.classList.toggle('active');
    menuToggle.classList.toggle('active');
  });

  overlay.addEventListener('click', closeMenu);

  document.addEventListener('click', (e) => {
    if (!navLinks.contains(e.target) && !menuToggle.contains(e.target)) {
      closeMenu();
    }
  });

  document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });

  function closeMenu() {
    navLinks.classList.remove('active');
    overlay.classList.remove('active');
    menuToggle.classList.remove('active');
  }
}

function highlightActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(link => {
    const href = link.getAttribute('href');
    if (href === path || (path === '/' && href === '/')) {
      link.style.color = 'var(--primary)';
    }
  });
}

// Load header and footer
document.addEventListener("DOMContentLoaded", () => {
  loadComponent("header", "/static/header.html");
  loadComponent("footer", "/static/footer.html");
  initScrollAnimations();
});

function initFooterForm() {
  const form = document.getElementById("contactForm");
  if (!form) return;

  form.addEventListener("submit", function(e) {
    e.preventDefault();

    const formData = new FormData(form);

    fetch(form.action, {
      method: "POST",
      body: formData,
      headers: { 'Accept': 'application/json' }
    })
    .then(response => {
      if (response.ok) {
        showSuccessPopup();
        form.reset();
      } else {
        alert("Something went wrong. Please try again.");
      }
    })
    .catch(() => {
      alert("Network error. Please try again.");
    });
  });
}

function showSuccessPopup() {
  let popup = document.getElementById("successPopup");

  if (!popup) {
    popup = document.createElement("div");
    popup.id = "successPopup";
    popup.className = "popup-overlay";
    popup.innerHTML = `
      <div class="popup-message">
        We will get back to you shortly.
      </div>
    `;
    document.body.appendChild(popup);
    popup.addEventListener("click", function() {
      popup.classList.remove("active");
    });
  }

  popup.classList.add("active");
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener("click", function(e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute("href"));
    if (target) {
      target.scrollIntoView({ behavior: "smooth" });
    }
  });
});

// Header scroll effect
window.addEventListener("scroll", function () {
  const header = document.getElementById("header");
  if (!header) return;

  if (window.scrollY > 40) {
    header.classList.add("scrolled");
  } else {
    header.classList.remove("scrolled");
  }
});

// Scroll-triggered fade-in animations
function initScrollAnimations() {
  const elements = document.querySelectorAll('.fade-up');
  if (elements.length === 0) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -40px 0px'
  });

  elements.forEach(el => observer.observe(el));
}
