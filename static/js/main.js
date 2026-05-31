const container = document.querySelector('.container');
const registerBtn = document.querySelector('.register-btn');
const loginBtn = document.querySelector('.login-btn');

registerBtn.addEventListener('click', () => {
    container.classList.add('active');
});

loginBtn.addEventListener('click', () => {
    container.classList.remove('active');
});

// Form validation
const loginForm = document.getElementById('loginForm');

loginForm.addEventListener('submit', function (event) {
    if (!loginForm.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
    }
    loginForm.classList.add('was-validated');
}); 