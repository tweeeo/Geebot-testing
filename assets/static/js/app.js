// Utilidades generales para el sitio web del bot

// Función para cerrar la ventana actual
function closeWindow() {
    // Intentar cerrar la ventana/pestaña
    try {
        // Mostrar mensaje antes de cerrar
        showToast('Cerrando ventana...', 'info');
        
        // Intentar cerrar la ventana
        window.close();
        
        // Si no se puede cerrar (por restricciones del navegador), redirigir
        setTimeout(() => {
            if (!window.closed) {
                // Mostrar mensaje alternativo
                showToast('Puedes cerrar esta pestaña manualmente', 'info');
                
                // Opcional: redirigir a Discord o página principal
                // window.location.href = 'https://discord.com';
            }
        }, 1000);
        
    } catch (error) {
        console.log('No se pudo cerrar la ventana automáticamente');
        showToast('Puedes cerrar esta pestaña manualmente', 'info');
    }
}

// Función para copiar texto al portapapeles
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copiado al portapapeles', 'success');
    }).catch(err => {
        console.error('Error al copiar:', err);
        showToast('Error al copiar', 'error');
    });
}

// Función para mostrar notificaciones toast
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        animation: slideInToast 0.3s ease-out;
        font-family: Inter, sans-serif;
        font-weight: 500;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOutToast 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// CSS para las animaciones de toast
const toastStyles = document.createElement('style');
toastStyles.textContent = `
    @keyframes slideInToast {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutToast {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(toastStyles);

// Función para animar elementos cuando aparecen en viewport
function animateOnScroll() {
    const elements = document.querySelectorAll('.animate-on-scroll');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeInUp 0.6s ease-out forwards';
            }
        });
    });
    
    elements.forEach(element => observer.observe(element));
}

// Función para mejorar la accesibilidad
function enhanceAccessibility() {
    // Añadir navegación por teclado a botones personalizados
    document.querySelectorAll('.close-button, .role-badge').forEach(element => {
        if (!element.hasAttribute('tabindex')) {
            element.setAttribute('tabindex', '0');
        }
        
        element.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                element.click();
            }
        });
    });
    
    // Mejorar el contraste en modo de alto contraste
    if (window.matchMedia('(prefers-contrast: high)').matches) {
        document.body.classList.add('high-contrast');
    }
}

// Función para manejar el tema oscuro/claro
function handleThemePreference() {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (prefersDark) {
        document.body.classList.add('dark-theme');
    }
    
    // Escuchar cambios en la preferencia de tema
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (e.matches) {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.remove('dark-theme');
        }
    });
}

// Función para añadir efectos de hover suaves
function addHoverEffects() {
    document.querySelectorAll('.role-badge, .close-button, .user-detail').forEach(element => {
        element.addEventListener('mouseenter', function() {
            this.style.transition = 'all 0.2s ease';
            this.style.transform = 'translateY(-2px) scale(1.02)';
        });
        
        element.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
}

// Función para manejar errores de imágenes
function handleImageErrors() {
    document.querySelectorAll('img').forEach(img => {
        img.addEventListener('error', function() {
            this.style.display = 'none';
        });
    });
}

// Función para añadir loading states
function addLoadingStates() {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('[type="submit"], .submit-button');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Procesando...';
                submitBtn.classList.add('loading');
            }
        });
    });
}

// Inicialización cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    animateOnScroll();
    enhanceAccessibility();
    handleThemePreference();
    addHoverEffects();
    handleImageErrors();
    addLoadingStates();
    
    // Preloader para mejorar la experiencia de carga
    const preloader = document.createElement('div');
    preloader.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #667eea;
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.3s ease;
    `;
    
    document.body.appendChild(preloader);
    
    // Remover preloader después de que la página esté completamente cargada
    window.addEventListener('load', () => {
        setTimeout(() => {
            preloader.remove();
        }, 500);
    });
});

// Función para analytics básicos (sin tracking personal)
function trackPageView() {
    const page = window.location.pathname;
    console.log(`Page view: ${page}`);
    
    // Aquí podrías añadir Google Analytics o similar si lo necesitas
    // gtag('event', 'page_view', { page_title: document.title });
}

// Ejecutar analytics
trackPageView();