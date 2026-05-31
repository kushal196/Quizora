// Handle form submission
document.getElementById('test-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Validate all questions are answered
    const unansweredQuestions = [];
    const questions = document.querySelectorAll('.question-card');
    questions.forEach((question, index) => {
        const answered = question.querySelector('input[type="hidden"]').value;
        if (!answered) {
            unansweredQuestions.push(index + 1);
        }
    });

    if (unansweredQuestions.length > 0) {
        alert(`Please answer question(s): ${unansweredQuestions.join(', ')}`);
        return;
    }
    
    // Submit the form
    const formData = new FormData(this);
    fetch(this.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            return response.json();
        }
    })
    .then(data => {
        if (data && data.error) {
            alert(data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while submitting the test');
    });
});

// Handle option selection
function selectOption(button, questionId, optionId) {
    // Remove selected class from all options in this question
    const questionCard = button.closest('.question-card');
    questionCard.querySelectorAll('.option-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    
    // Add selected class to clicked option
    button.classList.add('selected');
    
    // Update hidden input value
    const hiddenInput = questionCard.querySelector('input[type="hidden"]');
    hiddenInput.value = optionId;
    
    // Update progress
    updateProgress();
}

// Update progress bar
function updateProgress() {
    const totalQuestions = document.querySelectorAll('.question-card').length;
    const answeredQuestions = document.querySelectorAll('input[type="hidden"][value!=""]').length;
    const progress = (answeredQuestions / totalQuestions) * 100;
    document.getElementById('progress-bar').style.width = progress + '%';
}

// Initialize timer
let timeLeft = parseInt(document.getElementById('time').dataset.time);
const timerElement = document.getElementById('time');

function updateTimer() {
    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;
    timerElement.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

    if (timeLeft <= 0) {
        // Auto-submit the form
        document.getElementById('test-form').dispatchEvent(new Event('submit'));
    } else {
        timeLeft--;
    }
}

// Start timer
setInterval(updateTimer, 1000);
updateTimer();

// Function to display quiz results
function displayResults(results) {
    const questions = document.querySelectorAll('.question');
    let score = 0;

    questions.forEach((question, index) => {
        const options = question.querySelectorAll('input[type="radio"]');
        const result = results[index];

        options.forEach(option => {
            const label = option.nextElementSibling;
            if (option.value == result.correct_option) {
                label.classList.add('correct-answer');
            } else if (option.checked && option.value != result.correct_option) {
                label.classList.add('wrong-answer');
            }
            option.disabled = true;
        });

        if (result.is_correct) {
            score++;
        }
    });

    const scoreElement = document.createElement('div');
    scoreElement.classList.add('quiz-score');
    scoreElement.textContent = `Your score: ${score} / ${questions.length}`;
    document.getElementById('quiz-form').appendChild(scoreElement);
} 