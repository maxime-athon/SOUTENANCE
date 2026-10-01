// Script pour l'enregistrement audio dans le navigateur avec
//  visualisation de la forme d'onde et vumètre

let mediaRecorder;
let recordedChunks = [];
let timerInterval;
let startTime;
let selectedAudioInputId = null;
let visualizationFrameId;

const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const playBtn = document.getElementById('playBtn');
const recordingStatus = document.getElementById('recordingStatus');
const recordingTimer = document.getElementById('recordingTimer');
const timerDisplay = document.getElementById('timer');
const recordedAudio = document.getElementById('recordedAudio');
const recordingTimeDisplay = document.getElementById('recordingTimeDisplay');
const microphoneSelect = document.getElementById('microphoneSelect');
const recordingSourceMode = document.getElementById('recordingSourceMode');
const recordingNotification = document.getElementById('recordingNotification');
const fileInput = document.querySelector('input[type="file"]');

const EXTERNAL_INPUT_PATTERN = /usb|interface|audio|scarlett|focusrite|behringer|presonus|steinberg|zoom|m-audio|line|mix|card|sound/i;
let availableAudioInputs = [];

// Gestion des notifications d'état
function showRecordingNotification(type, message) {
    if (!recordingNotification) return;
    const iconClass = type === 'danger' ? 'fas fa-exclamation-triangle' : 'fas fa-exclamation-circle';
    recordingNotification.className = `alert alert-${type} small d-flex align-items-center gap-2 mb-3`;
    recordingNotification.replaceChildren(
        Object.assign(document.createElement('i'), { className: iconClass }),
        document.createTextNode(message)
    );
}

// Effacer la notification d'état
function clearRecordingNotification() {
    if (!recordingNotification) return;
    recordingNotification.className = 'alert alert-danger small d-none';
    recordingNotification.replaceChildren();
}

// Mettre à jour le statut d'enregistrement avec un message et une icône
function setRecordingStatus(type, message) {
    if (!recordingStatus) return;

    const icon = document.createElement('i');
    icon.className = {
        error: 'fas fa-exclamation-triangle text-danger me-1',
        warning: 'fas fa-exclamation-circle text-warning me-1',
        success: 'fas fa-check-circle text-success me-1',
        recording: 'fas fa-circle text-danger me-1',
        info: 'fas fa-info-circle text-muted me-1',
    }[type] || 'fas fa-info-circle text-muted me-1';

    recordingStatus.replaceChildren(icon, document.createTextNode(message));

    if (type === 'error') showRecordingNotification('danger', message);
    else if (type === 'warning') showRecordingNotification('warning', message);
    else clearRecordingNotification();
}

if (recordingTimeDisplay) recordingTimeDisplay.textContent = '00:00.00';

// Charger les entrées matérielles
async function loadMicrophones() {
    if (!microphoneSelect) return;

    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            throw new Error("Votre navigateur ne permet pas de détecter les périphériques audio.");
        }

        const devices = await navigator.mediaDevices.enumerateDevices();

        // Toutes les entrées audio disponibles sur l'ordinateur
        const audioInputs = devices.filter(
            device => device.kind === 'audioinput'
        );

        microphoneSelect.innerHTML = '';

        if (audioInputs.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Aucune entrée audio détectée';
            microphoneSelect.appendChild(option);

            selectedAudioInputId = null;

            if (recordBtn) {
                recordBtn.disabled = true;
            }

            return;
        }

        // Option par défaut
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '-- Sélectionner une entrée audio --';
        microphoneSelect.appendChild(defaultOption);

        // Ajouter TOUTES les entrées audio
        audioInputs.forEach((device, index) => {
            const option = document.createElement('option');

            option.value = device.deviceId;

            // Certains navigateurs peuvent ne pas donner le nom
            const label = device.label && device.label.trim()
                ? device.label
                : `Entrée audio ${index + 1}`;

            option.textContent = label;

            microphoneSelect.appendChild(option);
        });

        /*
         * Tentative de sélection automatique.
         * Cette partie ne sert qu'à choisir une entrée par défaut.
         * Elle ne limite PAS les périphériques disponibles.
         */
        const preferredInput = audioInputs.find(device => {
            const label = (device.label || '').toLowerCase();

            return EXTERNAL_INPUT_PATTERN.test(label);
        });

        if (preferredInput) {
            microphoneSelect.value = preferredInput.deviceId;
            selectedAudioInputId = preferredInput.deviceId;
        } else {
            // On ne sélectionne plus automatiquement "default".
            selectedAudioInputId = null;
            microphoneSelect.value = '';
        }

        if (recordBtn) {
            recordBtn.disabled = false;
        }

    } catch (error) {
        console.error("Erreur lors de la détection des entrées audio :", error);

        microphoneSelect.innerHTML = '';

        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Impossible de détecter les entrées audio';

        microphoneSelect.appendChild(option);

        selectedAudioInputId = null;
    }
}

// Gestionnaires d'événements UI
microphoneSelect?.addEventListener('change', (e) => {
    selectedAudioInputId = e.target.value || null;
    if (recordBtn) recordBtn.disabled = !selectedAudioInputId;
    if (selectedAudioInputId) {
        setRecordingStatus('info', 'Source prête. Cliquez sur « Enregistrer » pour commencer.');
    }
});

recordingSourceMode?.addEventListener('change', () => {
    const captureSystemAudio = recordingSourceMode.value === 'system';
    if (microphoneSelect) microphoneSelect.disabled = captureSystemAudio;
    if (recordBtn) recordBtn.disabled = captureSystemAudio ? false : !selectedAudioInputId;
    setRecordingStatus(
        'info',
        captureSystemAudio
            ? 'Mode audio ordinateur : le micro et les autres entrées ne seront pas enregistrés.'
            : 'Mode entrée audio : une seule source sélectionnée sera enregistrée.'
    );
});

// Initialisation Modale
const recModalEl = document.getElementById('recordingModeModal');
if (recModalEl) {
    const recModal = new bootstrap.Modal(recModalEl);
    const confirmStartRecordBtn = document.getElementById('confirmStartRecordBtn');

    recordBtn?.addEventListener('click', () => {
        recModal.show();
    });

    confirmStartRecordBtn?.addEventListener('click', async () => {
        recModal.hide();
        const selectedMode = document.querySelector('input[name="recModeRadio"]:checked')?.value || 'studio_mic';
        await startConfiguredRecording(selectedMode);
    });

    document.querySelectorAll('input[name="recModeRadio"]').forEach((radio) => {
        radio.addEventListener('change', (e) => {
            const hardwareContainer = document.getElementById('hardwareSelectContainer');
            if (!hardwareContainer) return;
            if (e.target.value === 'system_audio') {
                hardwareContainer.classList.add('d-none');
            } else {
                hardwareContainer.classList.remove('d-none');
            }
        });
    });
}

stopBtn?.addEventListener('click', stopRecording);
playBtn?.addEventListener('click', playRecording);

// Enregistrement Configuré
async function startConfiguredRecording(mode) {
    try {
        let stream;
        let sourceStream;

        if (mode === 'line_in') {
            const selectedCardId = microphoneSelect ? microphoneSelect.value : null;
            if (!selectedCardId || selectedCardId === 'default') {
                alert("Veuillez sélectionner votre carte son / entrée ligne dans la liste déroulante avant de démarrer.");
                return;
            }
            sourceStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    deviceId: selectedCardId ? { ideal: selectedCardId } : undefined,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false
                }
            });
            stream = sourceStream;
        } else if (mode === 'studio_mic') {
            const selectedCardId = microphoneSelect ? microphoneSelect.value : null;
            sourceStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    deviceId: selectedCardId && selectedCardId !== 'default' ? { exact: selectedCardId } : undefined,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                }
            });
            stream = sourceStream;
        } else if (mode === 'system_audio') {
            sourceStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
            if (sourceStream.getAudioTracks().length === 0) {
                sourceStream.getTracks().forEach((track) => track.stop());
                throw new Error('Aucun audio ordinateur reçu. Cochez "Partager l’audio" dans la fenêtre.');
            }
            stream = new MediaStream(sourceStream.getAudioTracks());
        } else if (mode === 'multitrack') {
            const sysStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
            const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mixContext = new (window.AudioContext || window.webkitAudioContext)();
            const destination = mixContext.createMediaStreamDestination();

            if (sysStream.getAudioTracks().length > 0) {
                mixContext.createMediaStreamSource(sysStream).connect(destination);
            }
            mixContext.createMediaStreamSource(micStream).connect(destination);

            sourceStream = sysStream;
            stream = destination.stream;
        }

        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = audioContext.createAnalyser();
        const microphone = audioContext.createMediaStreamSource(stream);

        let _recLeftChunks = [];
        let _recRightChunks = [];
        let _recTotalSamples = 0;
        const _recSampleRate = audioContext.sampleRate;
        let _recProcessor = null;

        try {
            const bufferSize = 4096;
            _recProcessor = audioContext.createScriptProcessor(bufferSize, 2, 2);
            microphone.connect(_recProcessor);
            try { _recProcessor.connect(audioContext.destination); } catch (e) { }

            _recProcessor.onaudioprocess = (e) => {
                const inL = e.inputBuffer.getChannelData(0);
                const inR = e.inputBuffer.numberOfChannels > 1 ? e.inputBuffer.getChannelData(1) : inL;
                _recLeftChunks.push(new Float32Array(inL));
                _recRightChunks.push(new Float32Array(inR));
                _recTotalSamples += inL.length;
            };
        } catch (err) {
            console.warn('Realtime PCM capture not available:', err);
        }

        microphone.connect(analyser);
        analyser.fftSize = 2048;

        mediaRecorder = new MediaRecorder(stream);
        recordedChunks = [];
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) recordedChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            const blob = new Blob(recordedChunks, { type: 'audio/webm' });
            const audioUrl = URL.createObjectURL(blob);
            if (recordedAudio) recordedAudio.src = audioUrl;

            const file = new File([blob], `recording_${Date.now()}.webm`, { type: 'audio/webm' });
            if (fileInput) {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInput.files = dataTransfer.files;
            }

            if (typeof window.extractAudioContextData === 'function') {
                window.extractAudioContextData(file, {
                    durationInput: document.querySelector('input[name="duration"]'),
                    speedInput: document.querySelector('input[name="speed"]') || document.querySelector('select[name="speed"]'),
                    propDuration: document.getElementById('audioDuration'),
                    propSampleRate: document.getElementById('audioSampleRate'),
                    propChannels: document.getElementById('audioChannels'),
                    previewDuration: document.getElementById('previewDuration'),
                    previewSpeed: document.getElementById('previewSpeed')
                });
            }

            try {
                if (window.audioEditor) {
                    if (!window.audioEditor.audioContext) {
                        window.audioEditor.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    }

                    if (_recTotalSamples > 0) {
                        const finalBuffer = window.audioEditor.audioContext.createBuffer(2, _recTotalSamples, _recSampleRate);
                        const outL = finalBuffer.getChannelData(0);
                        const outR = finalBuffer.getChannelData(1);
                        let offset = 0;
                        for (let i = 0; i < _recLeftChunks.length; i++) {
                            outL.set(_recLeftChunks[i], offset);
                            outR.set(_recRightChunks[i], offset);
                            offset += _recLeftChunks[i].length;
                        }

                        window.audioEditor.audioBuffer = finalBuffer;
                        window.audioEditor.currentTime = 0;
                        window.audioEditor.selection_start = 0;
                        window.audioEditor.selection_end = 0;
                        window.audioEditor.updateAudioProperties();
                        window.audioEditor.drawWaveform();
                        window.audioEditor.saveToHistory(false);
                    }
                }
            } catch (err) {
                console.warn('Failed to create AudioBuffer:', err);
            }

            if (typeof window.handleFileSelect === 'function') {
                window.handleFileSelect(true);
            }

            sourceStream?.getTracks().forEach(track => track.stop());

            try { if (_recProcessor) { _recProcessor.disconnect(); _recProcessor.onaudioprocess = null; } } catch (e) { }
            try { audioContext.close(); } catch (e) { }
            cancelAnimationFrame(visualizationFrameId);
        };

        mediaRecorder.start();
        startTime = Date.now();
        updateTimer();
        timerInterval = setInterval(updateTimer, 100);

        if (recordBtn) recordBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
        if (playBtn) playBtn.disabled = true;
        setRecordingStatus('recording', 'Enregistrement en cours...');
        if (recordingTimer) recordingTimer.style.display = 'block';
        if (recordedAudio) recordedAudio.style.display = 'none';

        visualizeRecordingWaveform(microphone, analyser);

    } catch (error) {
        console.error('Error starting recording:', error);
        if (recordBtn) recordBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        setRecordingStatus('error', `Enregistrement impossible : ${error.message || 'erreur source'}`);
    }
}

// Waveform Canvas & VU-Meter logic
let vuState = {
    left: { smoothed: 0, peak: 0, peakTime: 0 },
    right: { smoothed: 0, peak: 0, peakTime: 0 }
};
const VU_PEAK_HOLD_MS = 800;

function visualizeRecordingWaveform(sourceNode, analyser) {
    const canvas = document.getElementById('waveformCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const audioContext = sourceNode.context;
    const channelSplitter = audioContext.createChannelSplitter(2);

    try { sourceNode.connect(channelSplitter); } catch (e) { }
    try { sourceNode.connect(analyser); } catch (e) { }

    const leftAnalyser = audioContext.createAnalyser();
    const rightAnalyser = audioContext.createAnalyser();
    leftAnalyser.fftSize = rightAnalyser.fftSize = 2048;
    channelSplitter.connect(leftAnalyser, 0);
    channelSplitter.connect(rightAnalyser, 1);

    const leftData = new Uint8Array(leftAnalyser.fftSize / 2);
    const rightData = new Uint8Array(rightAnalyser.fftSize / 2);

    const displayWidth = Math.max(1, Math.floor(rect.width));
    const smoothLeft = new Float32Array(displayWidth).fill(0);
    const smoothRight = new Float32Array(displayWidth).fill(0);

   function drawChannelWaveform(channelData, yOffset, chHeight, smoothBuf) {
    const len = channelData.length;
    const samplesPerPixel = Math.max(1, Math.floor(len / displayWidth));
    const AMPLIFICATION = 1.5; // Boost de l'amplitude pour voir nettement les ondes

    const minVals = new Float32Array(displayWidth);
    const maxVals = new Float32Array(displayWidth);

    for (let x = 0; x < displayWidth; x++) {
        let min = 1.0, max = -1.0;
        const start = Math.floor(x * samplesPerPixel);
        for (let s = start; s < Math.min(len, start + samplesPerPixel); s++) {
            // Normalisation (-1 à 1) + Amplification
            let v = ((channelData[s] - 128) / 128) * AMPLIFICATION;
            v = Math.max(-1, Math.min(1, v)); // Clamp entre -1 et 1
            if (v < min) min = v;
            if (v > max) max = v;
        }
        minVals[x] = min === 1.0 ? 0 : min;
        maxVals[x] = max === -1.0 ? 0 : max;
    }

    const centerY = yOffset + chHeight / 2;

    // 1. Dessin de l'enveloppe d'onde remplie (Effet Montagne / Vague)
    ctx.beginPath();
    for (let x = 0; x < displayWidth; x++) {
        const yTop = centerY - maxVals[x] * (chHeight / 2);
        if (x === 0) ctx.moveTo(x, yTop);
        else ctx.lineTo(x, yTop);
    }
    for (let x = displayWidth - 1; x >= 0; x--) {
        const yBot = centerY - minVals[x] * (chHeight / 2);
        ctx.lineTo(x, yBot);
    }
    ctx.closePath();

    // Remplissage avec la couleur vert de votre charte graphique (#225A40)
    const envGrad = ctx.createLinearGradient(0, yOffset, 0, yOffset + chHeight);
    envGrad.addColorStop(0, 'rgba(34, 90, 64, 0.45)');
    envGrad.addColorStop(0.5, 'rgba(34, 90, 64, 0.15)');
    envGrad.addColorStop(1, 'rgba(34, 90, 64, 0.45)');
    ctx.fillStyle = envGrad;
    ctx.fill();

    // 2. Tracé du contour supérieur et inférieur (Contour net de l'onde)
    ctx.beginPath();
    for (let x = 0; x < displayWidth; x++) {
        const yTop = centerY - maxVals[x] * (chHeight / 2);
        if (x === 0) ctx.moveTo(x, yTop);
        else ctx.lineTo(x, yTop);
    }
    for (let x = displayWidth - 1; x >= 0; x--) {
        const yBot = centerY - minVals[x] * (chHeight / 2);
        if (x === displayWidth - 1) ctx.moveTo(x, yBot);
        else ctx.lineTo(x, yBot);
    }
    ctx.strokeStyle = '#225A40';
    ctx.lineWidth = 1.5;
    ctx.stroke();
}

    function draw() {
        visualizationFrameId = requestAnimationFrame(draw);

        leftAnalyser.getByteTimeDomainData(leftData);
        rightAnalyser.getByteTimeDomainData(rightData);

        let sumR = 0;
        for (let i = 0; i < rightData.length; i++) sumR += rightData[i];
        if (sumR === (128 * rightData.length) || sumR === 0) {
            rightData.set(leftData.subarray(0, rightData.length));
        }

        ctx.clearRect(0, 0, rect.width, rect.height);
        ctx.fillStyle = '#f8f9fa';
        ctx.fillRect(0, 0, rect.width, rect.height);

        const chHeight = Math.floor(rect.height / 2) - 6;
        drawChannelWaveform(leftData, 6, chHeight, smoothLeft);
        drawChannelWaveform(rightData, chHeight + 12, chHeight, smoothRight);

        updateVUMeter(leftData, rightData);
    }

    draw();
}

const VU_SEGMENTS_COUNT = 40;

function createVUSegments() {
    const containers = [document.getElementById('vuLeft'), document.getElementById('vuRight')];
    containers.forEach(container => {
        if (!container) return;
        container.innerHTML = '';
        for (let i = 0; i < VU_SEGMENTS_COUNT; i++) {
            const segment = document.createElement('div');
            segment.className = 'vu-segment';
            const percent = (i / VU_SEGMENTS_COUNT) * 100;
            if (percent < 70) segment.classList.add('green');
            else if (percent < 85) segment.classList.add('yellow');
            else segment.classList.add('red');
            container.appendChild(segment);
        }
    });
}
createVUSegments();

function updateVUMeter(leftData, rightData) {
    const calculateRMS = (data) => {
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
            const amplitude = (data[i] - 128) / 128;
            sum += amplitude * amplitude;
        }
        return Math.sqrt(sum / (data.length || 1));
    };

    const leftRMS = calculateRMS(leftData);
    const rightRMS = calculateRMS(rightData);
    const rmsToDb = (rms) => 20 * Math.log10(rms + 1e-6);

    const dbLeft = rmsToDb(leftRMS);
    const dbRight = rmsToDb(rightRMS);

    const dbToPercent = (db) => Math.max(0, Math.min(100, ((db - (-60)) / 66) * 100));

    const leftPct = dbToPercent(dbLeft);
    const rightPct = dbToPercent(dbRight);

    const now = performance.now();
    const smooth = (val, target) => val + (target - val) * (target > val ? 0.7 : 0.15);

    vuState.left.smoothed = smooth(vuState.left.smoothed, leftPct);
    vuState.right.smoothed = smooth(vuState.right.smoothed, rightPct);

    [vuState.left, vuState.right].forEach(state => {
        if (state.smoothed > state.peak) {
            state.peak = state.smoothed;
            state.peakTime = now;
        } else if (now - state.peakTime > VU_PEAK_HOLD_MS) {
            state.peak = Math.max(0, state.peak - 0.8);
        }
    });

    updateBars('vuLeft', vuState.left.smoothed, vuState.left.peak);
    updateBars('vuRight', vuState.right.smoothed, vuState.right.peak);

    const leftDbEl = document.getElementById('vuLeftDb');
    const rightDbEl = document.getElementById('vuRightDb');
    if (leftDbEl) leftDbEl.textContent = dbLeft <= -60 ? '-∞' : `${dbLeft.toFixed(1)} dB`;
    if (rightDbEl) rightDbEl.textContent = dbRight <= -60 ? '-∞' : `${dbRight.toFixed(1)} dB`;
}

function updateBars(containerId, percentage, peakPercentage) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const segments = container.children;
    const total = segments.length;
    const activeLimit = Math.floor((percentage / 100) * total);
    const peakIdx = Math.floor((peakPercentage / 100) * (total - 1));

    for (let i = 0; i < total; i++) {
        const seg = segments[i];
        if (i < activeLimit) seg.classList.add('active');
        else seg.classList.remove('active');

        if (i === peakIdx && peakIdx > 0) seg.classList.add('peak');
        else seg.classList.remove('peak');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        clearInterval(timerInterval);

        if (recordBtn) recordBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        if (playBtn) playBtn.disabled = false;
        setRecordingStatus('success', 'Enregistrement terminé');
        if (recordingTimer) recordingTimer.style.display = 'none';
        if (recordedAudio) recordedAudio.style.display = 'block';
    }
}

function playRecording() {
    if (recordedAudio && recordedAudio.src) {
        recordedAudio.play();
    }
}

function updateTimer() {
    const elapsed = Date.now() - startTime;
    const totalSeconds = Math.floor(elapsed / 1000);
    const centiseconds = Math.floor((elapsed % 1000) / 10);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${centiseconds.toString().padStart(2, '0')}`;

    if (timerDisplay) timerDisplay.textContent = timeString;
    if (recordingTimeDisplay) recordingTimeDisplay.textContent = timeString;
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Demande l'autorisation afin que le navigateur puisse
        // généralement fournir les noms des périphériques.
        await navigator.mediaDevices.getUserMedia({
            audio: true
        });
    } catch (error) {
        console.warn("Autorisation microphone non accordée :", error);
    }

    await loadMicrophones();
});