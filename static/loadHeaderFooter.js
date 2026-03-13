// loadHeaderFooter.js

async function loadComponent(id, file) {
  try {
    const response = await fetch(file);
    const html = await response.text();
    document.getElementById(id).innerHTML = html;

    // Attach toggle logic only when header is loaded
    if (id === "header") {
      initHamburgerToggle();
    }

    // Email Send Logic only when footer is loaded
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

  if (!menuToggle || !navLinks || !overlay) {
    console.error("Hamburger toggle elements not found in header.");
    return;
  }

  // Toggle menu open/close
  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    navLinks.classList.toggle('active');
    overlay.classList.toggle('active');
    menuToggle.classList.toggle('active');   // ⭐ for hamburger → X
  });

  // Close menu when overlay is clicked
  overlay.addEventListener('click', closeMenu);

  // Close menu when clicking anywhere outside the menu
  document.addEventListener('click', (e) => {
    if (!navLinks.contains(e.target) && !menuToggle.contains(e.target)) {
      closeMenu();
    }
  });

  // Close menu when a link is clicked
  document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });

  function closeMenu() {
    navLinks.classList.remove('active');
    overlay.classList.remove('active');
    menuToggle.classList.remove('active');
  }
}

// Load header and footer on page load
document.addEventListener("DOMContentLoaded", () => {
  loadComponent("header", "/static/header.html");
  loadComponent("footer", "/static/footer.html");
});

function initFooterForm() {
  const form = document.getElementById("contactForm");
  console.log("Footer form found:", form);
  if (!form) return;

  form.addEventListener("submit", function(e) {
    e.preventDefault();

    const formData = new FormData(form);

    fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        'Accept': 'application/json'
      }
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

  // Create popup only once
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

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener("click", function(e) {
    e.preventDefault();

    document.querySelector(this.getAttribute("href")).scrollIntoView({
      behavior: "smooth"
    });
  });
});

window.addEventListener("scroll", function () {

  const header = document.getElementById("header");

  if (window.scrollY > 40) {
      header.classList.add("scrolled");
  } else {
      header.classList.remove("scrolled");
  }

});