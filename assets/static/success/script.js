// Forzar cierre al dar clic en el botón
const btn = document.getElementById('closeWinBtn');
if (btn) {
  btn.addEventListener('click', () => {
    window.open('', '_self'); // Hack para algunos navegadores
    window.close();
  });
}

// Contador y cierre automático
let seconds = 3;
const countdownText = document.getElementById('countdownText');

const interval = setInterval(() => {
  seconds--;
  if (seconds > 0) {
    if (countdownText) countdownText.textContent = `Esta ventana se cerrará en ${seconds} segundos...`;
  } else {
    clearInterval(interval);
    window.open('', '_self'); // Hack antes del cierre
    window.close();
  }
}, 1000);