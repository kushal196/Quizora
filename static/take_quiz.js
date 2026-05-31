document.getElementById('quiz-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Validate all questions are answered
    const unansweredQuestions = [];
    const questions = document.querySelectorAll('.question');
    questions.forEach((question, index) => {
        // Removed unused variable 'questionId'
        const answered = question.querySelector('input[type="radio"]:checked');
        if (!answered) {
            unansweredQuestions.push(index + 1);
        }
    });

    if (unansweredQuestions.length > 0) {
        alert(`Please answer question(s): ${unansweredQuestions.join(', ')}`);
        return;
    }
    
    const formData = new FormData(this);
    const testId = document.getElementById('quiz-form').dataset.testId;
    
    fetch(`/submit_test/${testId}`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('Quiz submitted successfully!');
            displayResults(data.results); // Pass the results to displayResults
        } else {
            alert(data.error || 'Error submitting quiz. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error submitting quiz. Please try again.');
    });
});

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