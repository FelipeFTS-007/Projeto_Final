{% block extra_js %}
<!-- ✅ CARREGAR PYODIDE - PYTHON REAL NO NAVEGADOR -->
<script src="https://cdn.jsdelivr.net/pyodide/v0.23.4/full/pyodide.js"></script>
<script>
    // ===== SISTEMA DE LOOP DE QUESTÕES CORRIGIDO =====
    
    // Variáveis globais
    let questions = [];
    let currentQuestionIndex = 0;
    let totalQuestions = {{ aula.questoes.count }};
    let seconds = 0;
    let timerInterval;
    let totalXP = 0;
    let correctAnswers = 0;
    let usedHints = {};
    let userLives = parseInt(document.getElementById('vidas-restantes').value);
    let maxLives = parseInt(document.getElementById('max-vidas').value);
    let isReviewMode = document.getElementById('pratica-concluida').value === 'true';
    
    // ✅ SISTEMA DE CONTROLE CORRIGIDO
    let answeredCorrectly = new Set(); // Questões respondidas corretamente
    let pendingQuestions = new Set();  // Questões que ainda precisam ser respondidas
    let currentAttempts = {}; // Contador de tentativas por questão
    
    // ✅ VARIÁVEL PARA PYODIDE
    let pyodide = null;
    let isPyodideLoaded = false;
    
    // ===== INICIALIZAÇÃO =====
    document.addEventListener('DOMContentLoaded', async function() {
        console.log("🎯 Iniciando sistema de loop de questões CORRIGIDO...");
        
        // ✅ INICIALIZAR PYODIDE PRIMEIRO
        await initializePyodide();
        
        // Inicializar questões
        initializeQuestions();
        initializeHints();
        initializeQuestionEvents();
        initializeCodeEditors();
        initializeFillBlankQuestions();
        startTimer();
        updateProgress();
        
        // ✅ INICIALIZAR BOTÃO DE FINALIZAR REVISÃO
        initializeFinalizarRevisao();
        
        console.log(`✅ Sistema inicializado com ${totalQuestions} questões`);
        console.log(`🎯 Modo: ${isReviewMode ? 'REVISÃO' : 'NORMAL'}`);
        console.log(`❤️ Vidas iniciais: ${userLives}`);
    });

    // ===== INICIALIZAR BOTÃO FINALIZAR REVISÃO =====
    function initializeFinalizarRevisao() {
        const finalizarBtn = document.getElementById('finalizar-revisao-btn');
        if (finalizarBtn) {
            finalizarBtn.addEventListener('click', function() {
                if (isReviewMode) {
                    finishPractice();
                }
            });
        }
    }

    // ===== INICIALIZAR PYODIDE =====
    async function initializePyodide() {
        console.log("🐍 Iniciando Pyodide...");
        
        try {
            // Mostrar loading
            document.querySelectorAll('.terminal-content').forEach(terminal => {
                terminal.innerHTML = `
                    <div class="pyodide-loading">
                        <div class="spinner"></div>
                        <span>Carregando Python...</span>
                    </div>
                `;
            });
            
            // Carregar Pyodide
            pyodide = await loadPyodide({
                indexURL: "https://cdn.jsdelivr.net/pyodide/v0.23.4/full/"
            });
            
            // ✅ Configurar input/output corretamente
            await pyodide.runPythonAsync(`
                import sys
                import js
                
                class PythonInput:
                    def __init__(self):
                        self.buffer = ""
                    
                    def readline(self):
                        return "\\\\n"
                
                class PythonOutput:
                    def __init__(self):
                        self.content = ""
                    
                    def write(self, text):
                        self.content += text
                    
                    def flush(self):
                        pass
                
                sys.stdin = PythonInput()
                output_capture = PythonOutput()
                sys.stdout = output_capture
                sys.stderr = output_capture
            `);
            
            isPyodideLoaded = true;
            console.log("✅ Pyodide carregado com sucesso!");
            
            // Atualizar terminais
            document.querySelectorAll('.terminal-content').forEach(terminal => {
                terminal.innerHTML = '<div class="text-green-400">✅ Python carregado! Digite seu código e clique em "Executar".</div>';
            });
            
        } catch (error) {
            console.error("❌ Erro ao carregar Pyodide:", error);
            document.querySelectorAll('.terminal-content').forEach(terminal => {
                terminal.innerHTML = '<div class="text-red-400">❌ Erro ao carregar Python. Recarregue a página.</div>';
            });
        }
    }

    // ===== EXECUTAR CÓDIGO PYTHON REAL =====
    async function runPythonCode(code) {
        if (!isPyodideLoaded || !pyodide) {
            throw new Error("Python não está carregado ainda. Aguarde...");
        }
        
        try {
            await pyodide.runPythonAsync(`
                import sys
                import io
                
                output_capture = io.StringIO()
                sys.stdout = output_capture
                sys.stderr = output_capture
            `);
            
            await pyodide.runPythonAsync(code);
            
            const output = await pyodide.runPythonAsync(`
                output_text = output_capture.getvalue()
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                output_text
            `);
            
            return output || "";
            
        } catch (error) {
            const errorOutput = await pyodide.runPythonAsync(`
                try:
                    error_text = output_capture.getvalue()
                    sys.stdout = sys.__stdout__
                    sys.stderr = sys.__stderr__
                    error_text if error_text else "Erro durante a execução"
                except:
                    "Erro: ${error.message}"
            `);
            
            throw new Error(errorOutput || error.message);
        }
    }

    // ===== BUSCAR SAÍDA ESPERADA DA QUESTÃO =====
    function getExpectedOutputForQuestion(questionId) {
        console.log(`🔍 Buscando saída esperada para questão ${questionId}`);
        
        const questionElement = document.querySelector(`[data-question-id="${questionId}"]`);
        if (!questionElement) {
            console.error("Elemento da questão não encontrado");
            return "";
        }
        
        const saidaEsperadaElement = document.getElementById(`saida-esperada-${questionId}`);
        if (saidaEsperadaElement && saidaEsperadaElement.dataset.saidaEsperada) {
            const saida = saidaEsperadaElement.dataset.saidaEsperada.trim();
            console.log("✅ Saída esperada encontrada em data-saida-esperada:", saida);
            return saida;
        }
        
        const enunciado = questionElement.querySelector('.bg-gray-50, .enunciado, p');
        if (enunciado) {
            const texto = enunciado.textContent;
            const patterns = [
                /saída esperada[:\s]*([^\n\.]+)/i,
                /output esperado[:\s]*([^\n\.]+)/i,
                /resultado esperado[:\s]*([^\n\.]+)/i,
                /deve imprimir[:\s]*([^\n\.]+)/i,
                /deve retornar[:\s]*([^\n\.]+)/i
            ];
            
            for (let pattern of patterns) {
                const match = texto.match(pattern);
                if (match && match[1]) {
                    const saida = match[1].trim();
                    console.log("✅ Saída esperada extraída do enunciado:", saida);
                    return saida;
                }
            }
        }
        
        console.warn("⚠️ Nenhuma saída esperada encontrada para a questão");
        return "";
    }

    // ===== COMPARAÇÃO RIGOROSA DE SAÍDAS =====
    function areOutputsEqual(userOutput, expectedOutput) {
        if (!userOutput || !expectedOutput) {
            console.log("❌ Uma das saídas está vazia");
            return false;
        }
        
        const user = userOutput.toString().trim();
        const expected = expectedOutput.toString().trim();
        
        console.log(`🔍 Comparando: "${user}" vs "${expected}"`);
        
        // 1. Comparação exata (case-sensitive)
        if (user === expected) {
            console.log("✅ Comparação exata - CORRETO");
            return true;
        }
        
        // 2. Comparação case-insensitive
        if (user.toLowerCase() === expected.toLowerCase()) {
            console.log("✅ Comparação case-insensitive - CORRETO");
            return true;
        }
        
        // 3. Para números: comparar valores numéricos
        const userNum = parseFloat(user);
        const expectedNum = parseFloat(expected);
        
        if (!isNaN(userNum) && !isNaN(expectedNum)) {
            if (userNum === expectedNum) {
                console.log("✅ Comparação numérica - CORRETO");
                return true;
            }
        }
        
        // 4. Para múltiplas linhas: comparar linha por linha
        const userLines = user.split('\n').map(line => line.trim()).filter(line => line !== '');
        const expectedLines = expected.split('\n').map(line => line.trim()).filter(line => line !== '');
        
        if (userLines.length === expectedLines.length) {
            let todasLinhasIguais = true;
            for (let i = 0; i < userLines.length; i++) {
                if (userLines[i] !== expectedLines[i]) {
                    const userLineNum = parseFloat(userLines[i]);
                    const expectedLineNum = parseFloat(expectedLines[i]);
                    
                    if (isNaN(userLineNum) || isNaN(expectedLineNum) || userLineNum !== expectedLineNum) {
                        todasLinhasIguais = false;
                        break;
                    }
                }
            }
            if (todasLinhasIguais) {
                console.log("✅ Todas as linhas são iguais - CORRETO");
                return true;
            }
        }
        
        console.log("❌ Saídas diferentes - INCORRETO");
        return false;
    }

    // ===== SISTEMA DE QUESTÕES EM LOOP CORRIGIDO =====
    function initializeQuestions() {
        document.querySelectorAll('.question-container').forEach(container => {
            const questionId = container.dataset.questionId;
            questions.push({
                id: questionId,
                element: container,
                answered: false,
                correct: false
            });
            
            pendingQuestions.add(questionId);
            currentAttempts[questionId] = 0;
        });
        
        showQuestion(currentQuestionIndex);
    }
    
    function showQuestion(index) {
        document.querySelectorAll('.question-container').forEach(container => {
            container.classList.remove('active');
        });
        
        if (questions[index]) {
            questions[index].element.classList.add('active');
            updateQuestionIndicator(index);
            scrollToTop();
        }
    }
    
    function nextQuestion(isCorrect) {
        const currentQuestion = questions[currentQuestionIndex];
        const questionId = currentQuestion.id;
        
        console.log(`🔄 Próxima questão - Correto: ${isCorrect}, ID: ${questionId}`);
        
        if (isCorrect) {
            answeredCorrectly.add(questionId);
            pendingQuestions.delete(questionId);
            currentQuestion.answered = true;
            currentQuestion.correct = true;
            
            console.log(`✅ Questão ${currentQuestionIndex + 1} respondida corretamente`);
        } else {
            currentAttempts[questionId]++;
            currentQuestion.answered = false;
            currentQuestion.correct = false;
            
            console.log(`❌ Questão ${currentQuestionIndex + 1} incorreta. Tentativa ${currentAttempts[questionId]}`);
        }
        
        if (answeredCorrectly.size === totalQuestions) {
            console.log("🎉 Todas as questões respondidas corretamente!");
            finishPractice();
            return;
        }
        
        let nextIndex = findNextPendingQuestion();
        
        if (nextIndex === -1) {
            if (answeredCorrectly.size > 0) {
                console.log("🏁 Algumas questões corretas, mas não todas. Finalizando...");
                finishPractice();
            } else {
                console.log("🔄 Voltando para primeira questão pendente");
                nextIndex = findFirstPendingQuestion();
            }
        }
        
        if (nextIndex === -1) {
            console.log("💀 Nenhuma questão pode ser respondida - finalizando");
            finishPractice();
            return;
        }
        
        currentQuestionIndex = nextIndex;
        showQuestion(currentQuestionIndex);
        updateProgress();
        
        console.log(`➡️ Indo para questão ${currentQuestionIndex + 1}`);
        console.log(`📊 Progresso: ${answeredCorrectly.size}/${totalQuestions} corretas`);
        console.log(`⏳ Pendentes: ${pendingQuestions.size} questões`);
    }

    function findNextPendingQuestion() {
        for (let i = currentQuestionIndex + 1; i < questions.length; i++) {
            if (pendingQuestions.has(questions[i].id)) {
                return i;
            }
        }
        
        for (let i = 0; i < currentQuestionIndex; i++) {
            if (pendingQuestions.has(questions[i].id)) {
                return i;
            }
        }
        
        return -1;
    }

    function findFirstPendingQuestion() {
        for (let i = 0; i < questions.length; i++) {
            if (pendingQuestions.has(questions[i].id)) {
                return i;
            }
        }
        return -1;
    }

    function updateProgress() {
        const progress = (answeredCorrectly.size / totalQuestions) * 100;
        document.getElementById('practice-progress-fill').style.width = `${progress}%`;
        document.getElementById('progress-text').textContent = `${answeredCorrectly.size}/${totalQuestions}`;
        updateQuestionIndicator(currentQuestionIndex);
    }
    
    function updateQuestionIndicator(currentIndex) {
        document.querySelectorAll('.question-dot').forEach((dot, index) => {
            dot.classList.remove('current', 'answered', 'wrong');
            
            const questionId = questions[index]?.id;
            
            if (index === currentIndex) {
                dot.classList.add('current');
            } else if (answeredCorrectly.has(questionId)) {
                dot.classList.add('answered');
            } else if (pendingQuestions.has(questionId)) {
                // Ainda pendente - sem estilo especial
            } else {
                dot.classList.add('wrong');
            }
        });
    }

    // ===== EDITOR DE CÓDIGO =====
    function initializeCodeEditors() {
        document.querySelectorAll('.code-textarea').forEach(textarea => {
            const questionId = textarea.id.replace('code-input-', '');
            setupCodeEditor(questionId);
        });
    }
    
    function setupCodeEditor(questionId) {
        const textarea = document.getElementById(`code-input-${questionId}`);
        const lineNumbers = document.getElementById(`line-numbers-${questionId}`);
        
        if (!textarea) return;
        
        updateLineNumbers(textarea, lineNumbers);
        
        textarea.addEventListener('input', () => {
            updateLineNumbers(textarea, lineNumbers);
        });
        
        textarea.addEventListener('scroll', () => {
            lineNumbers.scrollTop = textarea.scrollTop;
        });
        
        textarea.addEventListener('keydown', handleEditorKeydown);
        
        const runBtn = document.querySelector(`.run-editor-code[data-question-id="${questionId}"]`);
        const checkBtn = document.querySelector(`.check-editor-code[data-question-id="${questionId}"]`);
        
        if (runBtn) {
            runBtn.addEventListener('click', () => handleRunEditorCode(questionId));
        }
        
        if (checkBtn) {
            checkBtn.addEventListener('click', () => handleCheckEditorCode(questionId));
        }
    }
    
    function updateLineNumbers(textarea, lineNumbers) {
        const lines = textarea.value.split('\n').length;
        let numbersHTML = '';
        
        for (let i = 1; i <= lines; i++) {
            numbersHTML += `<div class="line-number">${i}</div>`;
        }
        
        lineNumbers.innerHTML = numbersHTML;
        lineNumbers.style.height = textarea.scrollHeight + 'px';
    }
    
    function handleEditorKeydown(e) {
        const textarea = e.target;
        
        if (e.key === 'Tab') {
            e.preventDefault();
            
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            
            textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
            textarea.selectionStart = textarea.selectionEnd = start + 4;
            
            const questionId = textarea.id.replace('code-input-', '');
            const lineNumbers = document.getElementById(`line-numbers-${questionId}`);
            updateLineNumbers(textarea, lineNumbers);
            
            return false;
        }
    }

    // ===== VERIFICAÇÃO DE CÓDIGO EDITOR =====
    // ===== VERIFICAÇÃO DE CÓDIGO EDITOR - CORRIGIDA =====
    // ===== VERIFICAÇÃO DE CÓDIGO EDITOR - SIMPLIFICADA E FUNCIONAL =====
    async function handleCheckEditorCode(questionId) {
        console.log("=== 🔧 VERIFICAÇÃO DE CÓDIGO INICIADA ===");
        
        const textarea = document.getElementById(`code-input-${questionId}`);
        const terminal = document.getElementById(`code-output-${questionId}`);
        const questionContainer = document.querySelector(`[data-question-id="${questionId}"]`);
        
        if (!textarea || !terminal) {
            console.error("❌ Elementos não encontrados");
            return;
        }
        
        const userCode = textarea.value.trim();
        console.log("📝 Código do usuário:", userCode);
        
        if (!userCode) {
            showFeedback(questionId, 'incorrect', '❌ Digite algum código antes de verificar', 0);
            return;
        }
        
        // ✅ BUSCAR SAÍDA ESPERADA
        const expectedOutput = getExpectedOutputForQuestion(questionId);
        console.log("🎯 Saída esperada:", expectedOutput);
        
        const xp = 10; // XP fixo para simplificar
        
        // ✅ EXECUTAR CÓDIGO
        terminal.innerHTML = '<div class="text-yellow-400">🔧 Executando código...</div>';
        
        try {
            const output = await runPythonCode(userCode);
            const userOutput = output ? output.toString().trim() : "";
            console.log("📤 Saída do usuário:", userOutput);
            
            // ✅ VERIFICAR SE ESTÁ CORRETO
            let isCorrect = false;
            
            if (!expectedOutput || expectedOutput.trim() === "") {
                // Se não há saída esperada, considera correto se executou sem erro
                isCorrect = true;
                console.log("✅ Sem saída esperada - considerado correto");
            } else {
                // Comparação simples
                isCorrect = userOutput === expectedOutput.trim();
                console.log("🔍 Comparação:", isCorrect ? "CORRETO" : "INCORRETO");
            }
            
            if (isCorrect) {
                showFeedback(questionId, 'correct', '✅ Código correto! Parabéns!', xp);
                terminal.innerHTML = `<div class="text-green-400">${userOutput || "✅ Executado com sucesso!"}</div>`;
                totalXP += xp;
                
                setTimeout(() => {
                    nextQuestion(true);
                }, 1500);
            } else {
                showFeedback(questionId, 'incorrect', '❌ Código incorreto. Tente novamente.', 0);
                terminal.innerHTML = `<div class="text-red-400">
                    <strong>Sua saída:</strong> ${userOutput || "(nenhuma saída)"}
                    ${expectedOutput ? `\n<strong>Esperado:</strong> ${expectedOutput}` : ''}
                </div>`;
                
                if (!isReviewMode) {
                    await loseLife();
                }
                
                setTimeout(() => {
                    nextQuestion(false);
                }, 2000);
            }
            
        } catch (error) {
            console.error("❌ Erro na execução:", error);
            showFeedback(questionId, 'incorrect', '❌ Erro no código. Verifique a sintaxe.', 0);
            terminal.innerHTML = `<div class="text-red-400">Erro: ${error.message}</div>`;
            
            if (!isReviewMode) {
                await loseLife();
            }
            
            setTimeout(() => {
                nextQuestion(false);
            }, 2000);
        }
        
        console.log("=== 🔧 VERIFICAÇÃO FINALIZADA ===");
    }

    // ===== EXECUTAR CÓDIGO EDITOR =====
    async function handleRunEditorCode(questionId) {
        const textarea = document.getElementById(`code-input-${questionId}`);
        const terminal = document.getElementById(`code-output-${questionId}`);
        
        if (!textarea || !terminal) return;
        
        const code = textarea.value.trim();
        
        if (!code) {
            terminal.innerHTML = '<div class="text-yellow-400">Digite algum código para executar.</div>';
            return;
        }
        
        if (!isPyodideLoaded) {
            terminal.innerHTML = '<div class="text-yellow-400">Aguarde, Python ainda está carregando...</div>';
            return;
        }
        
        terminal.innerHTML = '<div class="text-yellow-400">🐍 Executando código Python...</div>';
        terminal.classList.remove('error');
        
        try {
            console.log("▶️ Executando código:", code);
            const output = await runPythonCode(code);
            console.log("✅ Output recebido:", output);
            
            let formattedOutput = output;
            if (!formattedOutput || formattedOutput.trim() === "") {
                formattedOutput = "✅ Código executado sem output.";
            }
            
            terminal.innerHTML = `<div style="white-space: pre-wrap; font-family: 'Courier New', monospace;" class="text-green-400">${formattedOutput}</div>`;
            terminal.classList.remove('error');
            
        } catch (error) {
            console.error("❌ Erro capturado:", error);
            terminal.innerHTML = `<div style="white-space: pre-wrap; font-family: 'Courier New', monospace;" class="text-red-400">${error.message}</div>`;
            terminal.classList.add('error');
        }
    }

    // ===== SISTEMA DE LACUNAS CORRIGIDO =====
    function initializeFillBlankQuestions() {
        document.querySelectorAll('[id^="fill-blank-text-"]').forEach(container => {
            const questionId = container.id.replace('fill-blank-text-', '');
            const originalText = container.textContent;
            
            const processedHTML = originalText.replace(/\[_____\]/g, 
                '<input type="text" class="blank-input" placeholder="______">'
            );
            
            container.innerHTML = processedHTML;
            
            container.style.whiteSpace = 'pre-wrap';
            container.style.wordWrap = 'break-word';
            container.style.lineHeight = '1.6';
            container.classList.add('fill-blank-container');
        });
    }

    async function handleCheckBlank(e) {
        const btn = e.currentTarget;
        const questionContainer = btn.closest('.question-container');
        const questionId = questionContainer.dataset.questionId;
        const xpElement = questionContainer.querySelector('.bg-yellow-100');
        const xp = xpElement ? parseInt(xpElement.textContent.match(/\d+/)[0]) : 10;
        
        console.log(`🔍 Verificando questão de lacunas: ${questionId}`);
        
        if (isReviewMode) {
            const blankInputs = questionContainer.querySelectorAll('.blank-input');
            const respostasCorretas = await getCorrectAnswersForQuestion(questionId);
            
            blankInputs.forEach((input, index) => {
                const respostaCorreta = respostasCorretas[index] || "Resposta não disponível";
                input.value = respostaCorreta;
                input.classList.add('blank-filled', 'correct-answer');
                input.disabled = true;
            });
            
            showFeedback(questionId, 'info', '📝 Modo revisão: Respostas corretas mostradas', 0);
            
            setTimeout(() => {
                nextQuestion(true);
            }, 2000);
            
            return;
        }
        
        const blankInputs = questionContainer.querySelectorAll('.blank-input');
        let allFilled = true;
        
        blankInputs.forEach(input => {
            if (!input.value.trim()) {
                allFilled = false;
                input.classList.add('shake');
                setTimeout(() => input.classList.remove('shake'), 500);
            }
        });
        
        if (!allFilled) {
            showFeedback(questionId, 'incorrect', '❌ Preencha todas as lacunas antes de verificar.', 0);
            return;
        }
        
        const respostasCorretas = await getCorrectAnswersForQuestion(questionId);
        console.log("Respostas corretas encontradas:", respostasCorretas);
        
        let isCorrect = true;
        let incorrectCount = 0;
        
        blankInputs.forEach(input => {
            input.classList.remove('correct-answer', 'wrong-answer', 'blank-filled');
        });
        
        blankInputs.forEach((input, index) => {
            const userAnswer = input.value.trim().toLowerCase();
            const correctAnswer = respostasCorretas[index] ? respostasCorretas[index].toString().toLowerCase() : "";
            
            console.log(`Lacuna ${index}: Usuário="${userAnswer}", Correto="${correctAnswer}"`);
            
            if (userAnswer === correctAnswer && correctAnswer !== "") {
                input.classList.add('correct-answer', 'blank-filled');
            } else {
                isCorrect = false;
                incorrectCount++;
                input.classList.add('wrong-answer', 'shake');
            }
        });
        
        if (isCorrect && respostasCorretas.length > 0) {
            showFeedback(questionId, 'correct', '✅ Todas as lacunas preenchidas corretamente!', xp);
            totalXP += xp;
            
            setTimeout(() => {
                nextQuestion(true);
            }, 1500);
        } else {
            const errorMessage = incorrectCount > 0 
                ? `❌ ${incorrectCount} lacuna(s) incorreta(s). Tente novamente.`
                : '❌ Respostas não conferem. Tente novamente.';
                
            showFeedback(questionId, 'incorrect', errorMessage, 0);
            
            if (!isReviewMode) {
                await loseLife();
            }
            
            setTimeout(() => {
                nextQuestion(false);
            }, 2000);
        }
    }

    // ===== FUNÇÃO PARA BUSCAR RESPOSTAS CORRETAS =====
    async function getCorrectAnswersForQuestion(questionId) {
        console.log(`🔍 Buscando respostas para questão ${questionId}`);
        
        try {
            const respostasElement = document.getElementById(`respostas-${questionId}`);
            if (respostasElement && respostasElement.dataset.respostas) {
                try {
                    const respostas = JSON.parse(respostasElement.dataset.respostas);
                    console.log("✅ Respostas encontradas no data attribute:", respostas);
                    return Array.isArray(respostas) ? respostas : [];
                } catch (e) {
                    console.error("❌ Erro ao parsear respostas:", e);
                }
            }
            
            const response = await fetch(`/api/questao/${questionId}/respostas/`);
            if (response.ok) {
                const data = await response.json();
                console.log("✅ Respostas da API:", data.respostas);
                return data.respostas || [];
            }
        } catch (error) {
            console.log("🔶 API não disponível, usando métodos alternativos");
        }
        
        const questionElement = document.querySelector(`[data-question-id="${questionId}"]`);
        if (questionElement) {
            const opcoesCorretas = questionElement.querySelectorAll('.option-button[data-correct="true"]');
            if (opcoesCorretas.length > 0) {
                const respostas = Array.from(opcoesCorretas).map(opcao => {
                    return opcao.textContent.trim();
                });
                console.log("✅ Respostas das opções corretas:", respostas);
                return respostas;
            }
        }
        
        console.warn("⚠️ Nenhuma resposta encontrada para a questão");
        return [];
    }

    // ===== SISTEMA DE DICAS =====
    function initializeHints() {
        document.querySelectorAll('.question-container').forEach(container => {
            const questionId = container.dataset.questionId;
            usedHints[questionId] = 0;
        });
    }
    
    function showHint(questionId) {
        const hintContainer = document.getElementById(`hints-${questionId}`);
        const hintSteps = hintContainer.querySelectorAll('.hint-step');
        const totalHints = hintSteps.length;
        
        if (totalHints === 0) {
            alert("Não há dicas disponíveis.");
            return;
        }
        
        if (usedHints[questionId] === 0) {
            hintContainer.style.display = 'block';
            usedHints[questionId] = 1;
        } else if (usedHints[questionId] < totalHints) {
            usedHints[questionId]++;
        } else {
            alert("Todas as dicas já foram mostradas!");
            return;
        }
        
        for (let i = 0; i < usedHints[questionId]; i++) {
            hintSteps[i].style.display = 'block';
        }
        
        const hintBtn = document.querySelector(`.hint-btn[data-question-id="${questionId}"]`);
        const counter = hintBtn.querySelector('.hint-counter');
        const remaining = totalHints - usedHints[questionId];
        
        counter.textContent = remaining;
        
        if (remaining === 0) {
            hintBtn.disabled = true;
            counter.classList.add('bg-red-500', 'text-white');
        }
    }

    // ===== MANIPULADORES DE RESPOSTAS =====
    function initializeQuestionEvents() {
        document.querySelectorAll('.hint-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const questionId = e.currentTarget.dataset.questionId;
                showHint(questionId);
            });
        });
        
        document.querySelectorAll('.option-button').forEach(btn => {
            btn.addEventListener('click', handleMultipleChoice);
        });
        
        document.querySelectorAll('.check-blank').forEach(btn => {
            btn.addEventListener('click', handleCheckBlank);
        });
    }
    
    function handleMultipleChoice(e) {
        const btn = e.currentTarget;
        const questionContainer = btn.closest('.question-container');
        const questionId = questionContainer.dataset.questionId;
        const isCorrect = btn.dataset.correct === 'true';
        const xp = parseInt(questionContainer.querySelector('.bg-yellow-100').textContent.match(/\d+/)[0]) || 10;
        
        if (isReviewMode) {
            questionContainer.querySelectorAll('.option-button').forEach(option => {
                if (option.dataset.correct === 'true') {
                    option.classList.add('correct-answer', 'bounce-in');
                }
                option.disabled = true;
            });
            
            showFeedback(questionId, 'info', '📝 Modo revisão: Resposta correta destacada', 0);
            
            setTimeout(() => {
                nextQuestion(true);
            }, 2000);
            
            return;
        }
        
        questionContainer.querySelectorAll('.option-button').forEach(option => {
            option.classList.remove('correct-answer', 'wrong-answer');
            option.disabled = true;
        });
        
        if (isCorrect) {
            btn.classList.add('correct-answer', 'bounce-in');
            showFeedback(questionId, 'correct', '✅ Resposta correta!', xp);
            totalXP += xp;
            
            setTimeout(() => {
                nextQuestion(true);
            }, 1500);
        } else {
            btn.classList.add('wrong-answer', 'shake');
            
            questionContainer.querySelectorAll('.option-button').forEach(option => {
                if (option.dataset.correct === 'true') {
                    option.classList.add('correct-answer');
                }
            });
            
            showFeedback(questionId, 'incorrect', '❌ Resposta incorreta.', 0);
            
            loseLife().then(() => {
                setTimeout(() => {
                    nextQuestion(false);
                }, 1500);
            });
        }
    }

    // ===== FUNÇÕES AUXILIARES =====
    async function loseLife() {
        if (isReviewMode) return false;
        
        if (userLives > 0) {
            userLives--;
            
            console.log(`💔 Vida perdida! Vidas restantes: ${userLives}`);
            
            showLifeLostMessage();
            
            const aulaId = document.getElementById('aula-id').value;
            
            try {
                const response = await fetch("{% url 'usar_vida_pratica' %}", {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{{ csrf_token }}'
                    },
                    body: JSON.stringify({
                        aula_id: aulaId
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    userLives = data.vidas_restantes;
                    console.log(`✅ Vidas atualizadas no servidor: ${userLives}`);
                }
            } catch (error) {
                console.error('❌ Erro na requisição:', error);
            }
            
            if (userLives <= 0) {
                console.log("💀 Sem vidas restantes - finalizando prática");
                setTimeout(() => {
                    endPracticeDueToLives();
                }, 2000);
            }
            
            return true;
        }
        
        return false;
    }
    
    function showLifeLostMessage() {
        const message = document.createElement('div');
        message.className = 'life-lost-message';
        message.innerHTML = `
            <div class="text-center">
                <div class="text-2xl mb-2">💔</div>
                <div>Você perdeu uma vida!</div>
                <div class="text-sm mt-1">Vidas restantes: ${userLives}/${maxLives}</div>
            </div>
        `;
        
        document.body.appendChild(message);
        
        setTimeout(() => {
            if (message.parentNode) {
                message.parentNode.removeChild(message);
            }
        }, 2000);
    }
    
    function showFeedback(questionId, type, message, xp) {
        const feedback = document.getElementById(`feedback-${questionId}`);
        feedback.innerHTML = message;
        feedback.className = `feedback-message feedback-${type} bounce-in`;
        feedback.classList.remove('hidden');
    }
    
    function scrollToTop() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    function startTimer() {
        timerInterval = setInterval(() => {
            seconds++;
            updateTimerDisplay();
        }, 1000);
    }
    
    function updateTimerDisplay() {
        let minutes = Math.floor(seconds / 60);
        let secs = seconds % 60;
        document.getElementById('timer').textContent = 
            String(minutes).padStart(2, '0') + ":" + String(secs).padStart(2, '0');
    }
    
    function stopTimer() {
        clearInterval(timerInterval);
        return seconds;
    }

    // ===== FINALIZAÇÃO CORRIGIDA =====
    async function finishPractice() {
        const aulaId = document.getElementById('aula-id').value;
        const elapsedTime = stopTimer();
        
        console.log(`🏁 Finalizando prática - Modo: ${isReviewMode ? 'REVISÃO' : 'NORMAL'}`);
        
        let xpFinal = 0;
        let timeBonus = 0;
        let revisaoBonus = 0;
        
        if (isReviewMode) {
            revisaoBonus = parseInt(document.getElementById('xp-revisao').value) || 5;
            xpFinal = revisaoBonus;
            
            console.log(`📝 Revisão: Bônus de ${revisaoBonus} XP`);
            
            try {
                await fetch("{% url 'registrar_xp_revisao' %}", {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{{ csrf_token }}'
                    },
                    body: JSON.stringify({
                        aula_id: aulaId,
                        xp_revisao: revisaoBonus
                    })
                });
            } catch (error) {
                console.error('❌ Erro ao registrar XP da revisão:', error);
            }
        } else {
            const expectedTime = {{ aula.tempo_pratica }} * 60;
            
            if (elapsedTime < expectedTime * 0.5) timeBonus = Math.floor(totalXP * 0.2);
            else if (elapsedTime < expectedTime * 0.8) timeBonus = Math.floor(totalXP * 0.1);
            
            xpFinal = totalXP + timeBonus;
            
            console.log(`🎯 Normal: XP=${totalXP}, Bônus=${timeBonus}, Total=${xpFinal}`);
            
            try {
                const response = await fetch("{% url 'finalizar_pratica' %}", {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{{ csrf_token }}'
                    },
                    body: JSON.stringify({
                        aula_id: aulaId,
                        xp_total: xpFinal,
                        vidas_restantes: userLives
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    console.log("✅ Prática finalizada com sucesso!");
                }
            } catch (error) {
                console.error('❌ Erro ao finalizar prática:', error);
            }
        }
        
        showResultScreen(xpFinal, elapsedTime, timeBonus, revisaoBonus);
    }
    
    function showResultScreen(totalXP, elapsedTime, timeBonus, revisaoBonus = 0) {
        const resultScreen = document.getElementById('result-screen');
        const questionsContainer = document.getElementById('questions-container');
        
        questionsContainer.style.display = 'none';
        resultScreen.classList.remove('hidden');
        
        if (isReviewMode) {
            resultScreen.querySelector('h2').innerHTML = '📝 Revisão Concluída';
            resultScreen.querySelector('p').textContent = 'Revisão dos exercícios finalizada!';
        }
        
        if (isReviewMode) {
            document.getElementById('final-xp').textContent = revisaoBonus;
            document.getElementById('time-bonus').textContent = '0';
        } else {
            document.getElementById('final-xp').textContent = totalXP - timeBonus;
            document.getElementById('time-bonus').textContent = timeBonus;
        }
        
        if (isReviewMode) {
            document.getElementById('revisao-bonus').textContent = revisaoBonus;
        }
        
        const minutes = Math.floor(elapsedTime / 60);
        const secondsRemaining = elapsedTime % 60;
        document.getElementById('final-time').textContent = 
            String(minutes).padStart(2, '0') + ':' + String(secondsRemaining).padStart(2, '0');
            
        console.log(`🏁 Tela de Resultados: Total XP=${totalXP}, Tempo=${minutes}:${secondsRemaining}, Revisão=${revisaoBonus}`);
    }
    
    function endPracticeDueToLives() {
        stopTimer();
        
        const resultScreen = document.getElementById('result-screen');
        const questionsContainer = document.getElementById('questions-container');
        
        questionsContainer.style.display = 'none';
        resultScreen.classList.remove('hidden');
        
        resultScreen.querySelector('h2').innerHTML = '💔 Fim da Prática';
        resultScreen.querySelector('p').textContent = 'Suas vidas acabaram! Tente novamente.';
        
        document.getElementById('final-xp').textContent = totalXP;
        document.getElementById('time-bonus').textContent = '0';
        
        const minutes = Math.floor(seconds / 60);
        const secondsRemaining = seconds % 60;
        document.getElementById('final-time').textContent = 
            String(minutes).padStart(2, '0') + ':' + String(secondsRemaining).padStart(2, '0');
        
        const restartBtn = resultScreen.querySelector('button[onclick="location.reload()"]');
        restartBtn.innerHTML = 'Tentar Novamente 🔄';
    }

    // Debug function
    function debugRespostas() {
        console.log("=== 🎯 DEBUG DE RESPOSTAS ===");
        
        document.querySelectorAll('.option-button[data-correct="true"]').forEach((btn, index) => {
            const texto = btn.querySelector('span:last-child').textContent;
            console.log(`✅ Opção Correta ${index + 1}: ${texto}`);
        });
        
        document.querySelectorAll('[id^="saida-esperada-"]').forEach(element => {
            const saida = element.dataset.saidaEsperada;
            if (saida) {
                console.log(`🐍 Saída Esperada: ${saida}`);
            }
        });
        
        document.querySelectorAll('[data-respostas]').forEach(element => {
            try {
                const respostas = JSON.parse(element.dataset.respostas);
                console.log(`📝 Respostas Lacunas:`, respostas);
            } catch (e) {
                console.log('❌ Erro ao parsear respostas de lacunas');
            }
        });
        
        console.log("=== 🎯 FIM DEBUG ===");
    }

    // Executar quando a página carregar
    document.addEventListener('DOMContentLoaded', debugRespostas);

    console.log("🚀 Sistema com Python real (Pyodide) carregado com sucesso!");
</script>
{% endblock %}