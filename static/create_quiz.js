let questionCount = 0;

function addQuestion() {
    questionCount++;
    const questionHtml = `
        <div class="question" id="question-${questionCount}">
            <h3>Question ${questionCount}</h3>
            <div class="form-group">
                <label for="question-${questionCount}-text">Question Text</label>
                <input type="text" id="question-${questionCount}-text" name="question-${questionCount}-text" required>
            </div>
            <div class="options-container">
                <div class="form-group">
                    <label for="question-${questionCount}-option-1">Option 1</label>
                    <input type="text" id="question-${questionCount}-option-1" name="question-${questionCount}-option-1" required>
                    <input type="radio" name="question-${questionCount}-correct" value="1" required>
                </div>
                <div class="form-group">
                    <label for="question-${questionCount}-option-2">Option 2</label>
                    <input type="text" id="question-${questionCount}-option-2" name="question-${questionCount}-option-2" required>
                    <input type="radio" name="question-${questionCount}-correct" value="2" required>
                </div>
                <div class="form-group">
                    <label for="question-${questionCount}-option-3">Option 3</label>
                    <input type="text" id="question-${questionCount}-option-3" name="question-${questionCount}-option-3" required>
                    <input type="radio" name="question-${questionCount}-correct" value="3" required>
                </div>
                <div class="form-group">
                    <label for="question-${questionCount}-option-4">Option 4</label>
                    <input type="text" id="question-${questionCount}-option-4" name="question-${questionCount}-option-4" required>
                    <input type="radio" name="question-${questionCount}-correct" value="4" required>
                </div>
            </div>
        </div>
    `;
    document.getElementById('questions-container').insertAdjacentHTML('beforeend', questionHtml);
}

document.getElementById('add-question').addEventListener('click', addQuestion);

document.getElementById('quiz-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Validate minimum questions
    if (questionCount < 1) {
        alert('Please add at least one question to the quiz.');
        return;
    }
    
    // Validate all questions have a selected correct answer
    const questions = document.querySelectorAll('.question');
    for (let i = 0; i < questions.length; i++) {
        const radioButtons = questions[i].querySelectorAll('input[type="radio"]');
        const selectedOption = Array.from(radioButtons).some(radio => radio.checked);
        if (!selectedOption) {
            alert(`Please select a correct answer for question ${i + 1}`);
            return;
        }
    }
    
    const formData = new FormData(this);
    fetch('/create_test', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Quiz created successfully!');
            window.location.href = '/admin';
        } else {
            alert(data.error || 'Error creating quiz. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error creating quiz. Please try again.');
    });
});

// Add initial question
addQuestion();