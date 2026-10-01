// Audio Editing Functionality (Cool Edit Pro style)
//cet class gère l'édition audio, y compris le zoom, la sélection, la lecture et les effets.
//elle est conçue pour être utilisée avec un canevas HTML5 pour afficher la forme d'onde et interagir avec l'utilisateur.
class AudioEditor {
    constructor() {
        this.audioContext = null;
        this.audioBuffer = null;
        this.canvas = document.getElementById('waveformCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.isPlaying = false;
        this.currentTime = 0;
        this.selection_start = 0;
        this.selection_end = 0;
        this.zoom = 1;
        this.scrollPosition = 0;
        this.clipboard = null;
        this.history = [];
        this.historyIndex = -1;
        this.isSelecting = false;
        this.isDirty = false;
        this.lastAmplifyValue = 0;
        this.currentFormat = 'Inconnu';
        this.playbackSource = null;
        this.loopMode = false;
        this.liveTimeUpdateInterval = null;
        this.isClickDisabled = false;
        this.mediaRecorder = null;
        this.recordedChunks = [];
        this.isRecording = false;

        this.initializeEventListeners();
        this.initializeCanvas();
    }


    async loadAudioFromUrl(url) {
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            const response = await fetch(url);
            const arrayBuffer = await response.arrayBuffer();
            this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            this.currentTime = 0;
            this.selection_start = 0;
            this.selection_end = 0;
            this.zoom = 1;
            this.scrollPosition = 0;
            this.clipboard = null;
            this.history = [];
            this.historyIndex = -1;
            this.isDirty = false;
            this.updateAudioProperties();
            this.drawWaveform();
            this.saveToHistory(false);
        } catch (error) {
            console.error('Erreur lors du chargement de l\'URL audio:', error);
        }
    }
    initializeEventListeners() {
        window.addEventListener('resize', () => this.initializeCanvas());

        // Keyboard navigation becomes active when the waveform is clicked.
        this.canvas.tabIndex = 0;

        // Keyboard shortcuts - listen on document only (to avoid multiple triggers)
        const keydownHandler = (e) => this.handleKeyDown(e);
        document.addEventListener('keydown', keydownHandler);

        // Waveform controls
        document.getElementById('zoomInBtn').addEventListener('click', () => this.zoomIn());
        document.getElementById('zoomOutBtn').addEventListener('click', () => this.zoomOut());
        document.getElementById('fitToViewBtn').addEventListener('click', () => this.fitToView());

        // Play/Stop Toggle
        document.getElementById('playStopBtn').addEventListener('click', () => this.togglePlayPause());

        // Recording controls are owned by audio_recorder.js. Keeping a single
        // handler prevents two simultaneous getUserMedia calls for one click.

        // Selection tools
        document.getElementById('selectAllBtn').addEventListener('click', () => this.selectAll());
        document.getElementById('clearSelectionBtn').addEventListener('click', () => this.clearSelection());

        // New Playback Controls
        document.getElementById('goToStartBtn').addEventListener('click', () => this.goToStart());
        document.getElementById('rewindBtn').addEventListener('click', (e) => {
            e.preventDefault();
            if (!this.isClickDisabled) {
                this.isClickDisabled = true;
                this.rewind();
                setTimeout(() => { this.isClickDisabled = false; }, 100);
            }
        });
        document.getElementById('playLoopBtn').addEventListener('click', () => this.toggleLoopMode());
        document.getElementById('fastForwardBtn').addEventListener('click', (e) => {
            e.preventDefault();
            if (!this.isClickDisabled) {
                this.isClickDisabled = true;
                this.fastForward();
                setTimeout(() => { this.isClickDisabled = false; }, 100);
            }
        });
        document.getElementById('goToEndBtn').addEventListener('click', () => this.goToEnd());

        // Edit operations
        document.getElementById('cutBtn').addEventListener('click', () => this.cut());
        document.getElementById('copyBtn').addEventListener('click', () => this.copy());
        document.getElementById('pasteBtn').addEventListener('click', () => this.paste());
        document.getElementById('deleteBtn').addEventListener('click', () => this.delete());
        document.getElementById('undoBtn').addEventListener('click', () => this.undo());
        document.getElementById('redoBtn').addEventListener('click', () => this.redo());
        document.getElementById('deleteSelectionBtn').addEventListener('click', () => this.delete());
        document.getElementById('trimBtn').addEventListener('click', () => this.trim());


        // Audio effects
        document.getElementById('fadeInBtn').addEventListener('click', () => this.fadeIn());
        document.getElementById('fadeOutBtn').addEventListener('click', () => this.fadeOut());
        document.getElementById('normalizeBtn').addEventListener('click', () => this.normalize());

        // Volume control
        document.getElementById('amplifySlider').addEventListener('input', (e) => this.amplify(parseFloat(e.target.value)));

        // Canvas interactions
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.handleMouseUp());
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
    }

    handleKeyDown(e) {
        // 1. Ignorer les raccourcis si l'utilisateur est en train de taper dans un champ du formulaire
        const activeElement = document.activeElement;
        const isInputElement = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.isContentEditable
        );

        if (isInputElement) {
            return;
        }

        // 2. Reste de la logique existante
        const waveformHasFocus = document.activeElement === this.canvas;
        if (waveformHasFocus && this.audioBuffer && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
            if (e.code === 'ArrowLeft') {
                e.preventDefault();
                this.scrollWaveform(-0.04);
                return;
            }
            if (e.code === 'ArrowRight') {
                e.preventDefault();
                this.scrollWaveform(0.04);
                return;
            }
            if (e.code === 'PageUp') {
                e.preventDefault();
                this.scrollWaveform(-0.8 / this.zoom);
                return;
            }
            if (e.code === 'PageDown') {
                e.preventDefault();
                this.scrollWaveform(0.8 / this.zoom);
                return;
            }
            if (e.code === 'Home') {
                e.preventDefault();
                this.scrollPosition = 0;
                this.drawWaveform();
                return;
            }
            if (e.code === 'End') {
                e.preventDefault();
                this.scrollPosition = this.getMaxScrollPosition();
                this.drawWaveform();
                return;
            }
        }

        // Ctrl+A to select all - Handle at top level
        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyA' || e.key === 'a' || e.key === 'A')) {
            if (this.audioBuffer) {
                e.preventDefault();
                this.selectAll();
                return;
            }
        }

        if (e.code === 'Space' && this.audioBuffer) {
            e.preventDefault();
            e.stopImmediatePropagation();
            this.togglePlayPause();
            return;
        }
        // Delete key to remove selection
        if (e.code === 'Delete' && this.audioBuffer && this.selection_start !== this.selection_end) {
            e.preventDefault();
            this.delete();
        }
        // Ctrl+Z to undo
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyZ' && this.audioBuffer) {
            e.preventDefault();
            this.undo();
        }
        // Ctrl+Y to redo
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyY' && this.audioBuffer) {
            e.preventDefault();
            this.redo();
        }
        // Shift + Arrow Left to extend selection to the left
        if (e.shiftKey && e.code === 'ArrowLeft' && this.audioBuffer) {
            e.preventDefault();
            this.extendSelectionLeft();
        }
        // Shift + Arrow Right to extend selection to the right
        if (e.shiftKey && e.code === 'ArrowRight' && this.audioBuffer) {
            e.preventDefault();
            this.extendSelectionRight();
        }
        // Ctrl+C to copy selection
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyC' && this.audioBuffer && this.selection_start !== this.selection_end) {
            e.preventDefault();
            this.copy();
        }
        // Ctrl+X to cut selection
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyX' && this.audioBuffer && this.selection_start !== this.selection_end) {
            e.preventDefault();
            this.cut();
        }
        // Ctrl+V to paste
        if ((e.ctrlKey || e.metaKey) && e.code === 'KeyV' && this.audioBuffer && this.clipboard) {
            e.preventDefault();
            this.paste();
        }
    }
    initializeCanvas() {
        if (!this.canvas) {
            return;
        }
        // Get the displayed size of the canvas
        const rect = this.canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        // Set the internal canvas size (in pixels)
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;

        // Reset before scaling; otherwise every window resize multiplies the scale.
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        this.drawWaveform();
    }

    async loadAudioFromFile(file) {
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            const arrayBuffer = await file.arrayBuffer();
            this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            this.currentTime = 0;
            this.selection_start = 0;
            this.selection_end = 0;
            this.zoom = 1;
            this.scrollPosition = 0;
            this.clipboard = null;
            this.history = [];
            this.historyIndex = -1;
            this.lastAmplifyValue = 0;
            this.isDirty = false;
            this.currentFormat = file.type || (file.name.split('.').pop() || 'Inconnu').toUpperCase();
            const slider = document.getElementById('amplifySlider');
            const sliderValue = document.getElementById('amplifyValue');
            if (slider) slider.value = 0;
            if (sliderValue) sliderValue.textContent = '0.0 dB';
            document.getElementById('undoBtn').disabled = true;
            document.getElementById('pasteBtn').disabled = true;
            this.updateAudioProperties();
            this.drawWaveform();
            const infoMessage = document.getElementById('noAudioMessage');
            if (infoMessage) {
                infoMessage.style.display = 'none';
            }
            this.saveToHistory(false);
        } catch (error) {
            console.error('Error loading audio:', error);
            alert('Erreur lors du chargement du fichier audio.');
        }
    }

    clearAudio() {
        this.stopPlayback();
        this.audioBuffer = null;
        this.history = [];
        this.historyIndex = -1;
        this.selection_start = 0;
        this.selection_end = 0;
        this.clipboard = null;
        this.isDirty = false;
        this.lastAmplifyValue = 0;
        this.currentFormat = 'Inconnu';
        this.loopMode = false;
        this.currentTime = 0;
        document.getElementById('undoBtn').disabled = true;
        document.getElementById('pasteBtn').disabled = true;
        const loopBtn = document.getElementById('playLoopBtn');
        if (loopBtn) {
            loopBtn.classList.remove('btn-success');
            loopBtn.classList.add('btn-outline-success');
        }
        const durationEl = document.getElementById('audioDuration');
        const sampleRateEl = document.getElementById('audioSampleRate');
        const channelsEl = document.getElementById('audioChannels');
        const formatEl = document.getElementById('audioFormat');
        const slider = document.getElementById('amplifySlider');
        const sliderValue = document.getElementById('amplifyValue');
        if (durationEl) durationEl.textContent = '00:00.000';
        if (sampleRateEl) sampleRateEl.textContent = '--';
        if (channelsEl) channelsEl.textContent = '--';
        if (formatEl) formatEl.textContent = '--';
        if (slider) slider.value = 0;
        if (sliderValue) sliderValue.textContent = '0.0 dB';
        const infoMessage = document.getElementById('noAudioMessage');
        if (infoMessage) {
            infoMessage.style.display = 'block';
        }
        this.updateLiveTimeDisplay();
        this.drawWaveform();
    }

    updateAudioProperties() {
        if (this.audioBuffer) {
            document.getElementById('audioDuration').textContent =
                AudioUtils.formatTime(this.audioBuffer.duration);
            document.getElementById('audioSampleRate').textContent = `${this.audioBuffer.sampleRate} Hz`;
            document.getElementById('audioChannels').textContent = this.audioBuffer.numberOfChannels;
            document.getElementById('audioFormat').textContent = this.currentFormat || 'Inconnu';
        }
    }

    drawWaveform() {
        if (!this.canvas || !this.ctx) return;

        // Display size (CSS pixels)
        const rect = this.canvas.getBoundingClientRect();
        const displayWidth = Math.floor(rect.width);
        const displayHeight = Math.floor(rect.height);

        // Clear & background
        this.ctx.clearRect(0, 0, displayWidth, displayHeight);
        this.ctx.fillStyle = '#f8f9fa';
        this.ctx.fillRect(0, 0, displayWidth, displayHeight);

        if (!this.audioBuffer) return;

        const channels = this.audioBuffer.numberOfChannels;
        const leftData = this.audioBuffer.getChannelData(0);
        const rightData = channels > 1 ? this.audioBuffer.getChannelData(1) : leftData;

        // Sampling & scroll
        const samplesPerPixel = Math.max(1, Math.floor(leftData.length / (displayWidth * this.zoom)));
        const scrollOffsetLeft = Math.floor(this.scrollPosition * leftData.length);
        const scrollOffsetRight = Math.floor(this.scrollPosition * rightData.length);

        // Visual theme
        const waveColor = '#225A40';            // cyan/teal
        const waveFillA = 'rgba(34,90,64,0.14)';
        const waveFillB = 'rgba(34,90,64,0.05)';
        const selectionFill = 'rgba(34,90,64,0.12)';
        const selectionBorder = 'rgba(34,90,64,0.6)';

        // Helper to draw one channel into a vertical slice
        const drawChannel = (channelData, yOffset, chHeight, label) => {
            const centerY = yOffset + chHeight / 2;
            const minYs = new Array(displayWidth);
            const maxYs = new Array(displayWidth);

            // compute min/max per pixel (respect scroll)
            const scrollOffset = Math.floor(this.scrollPosition * channelData.length);
            for (let x = 0; x < displayWidth; x++) {
                let min = 1.0, max = -1.0;
                const startSample = scrollOffset + Math.floor(x * samplesPerPixel);
                for (let s = startSample; s < startSample + samplesPerPixel && s < channelData.length; s++) {
                    const v = channelData[s];
                    if (v < min) min = v;
                    if (v > max) max = v;
                }

                const amplitude = (chHeight / 2) - 2; // padding
                minYs[x] = centerY + min * amplitude;
                maxYs[x] = centerY + max * amplitude;
            }

            // Fill waveform (between min/max)
            this.ctx.beginPath();
            this.ctx.moveTo(0, minYs[0] || centerY);
            for (let x = 1; x < displayWidth; x++) this.ctx.lineTo(x, minYs[x]);
            for (let x = displayWidth - 1; x >= 0; x--) this.ctx.lineTo(x, maxYs[x]);
            this.ctx.closePath();

            const grad = this.ctx.createLinearGradient(0, yOffset, 0, yOffset + chHeight);
            grad.addColorStop(0, waveFillA);
            grad.addColorStop(1, waveFillB);
            this.ctx.fillStyle = grad;
            this.ctx.fill();

            // Stroke outline
            this.ctx.lineWidth = 1.2;
            this.ctx.strokeStyle = waveColor;
            this.ctx.stroke();

            // Center line for the channel
            this.ctx.beginPath();
            this.ctx.moveTo(0, centerY);
            this.ctx.lineTo(displayWidth, centerY);
            this.ctx.lineWidth = 1;
            this.ctx.strokeStyle = 'rgba(0,0,0,0.08)';
            this.ctx.stroke();

            // Channel label
            this.ctx.font = '12px Inter, Arial, sans-serif';
            this.ctx.fillStyle = 'rgba(0,0,0,0.6)';
            this.ctx.fillText(label, 8, yOffset + 14);
        };

        // Layout: stacked channels when stereo, centered single when mono
        const gap = 8;
        if (channels > 1) {
            const half = Math.max(40, Math.floor((displayHeight - gap) / 2));
            drawChannel(leftData, 6, half - 6, 'Gauche');
            drawChannel(rightData, half + gap, half - 6, 'Droit');
        } else {
            drawChannel(leftData, 0, displayHeight, 'Mono');
        }

        // Selection overlay (covers both channels)
        if (this.selection_start !== this.selection_end) {
            const startX = Math.max(0, ((this.selection_start / this.audioBuffer.duration) * displayWidth) - this.scrollPosition * displayWidth);
            const endX = Math.min(displayWidth, ((this.selection_end / this.audioBuffer.duration) * displayWidth) - this.scrollPosition * displayWidth);
            const widthSel = Math.max(0, endX - startX);

            this.ctx.fillStyle = selectionFill;
            this.ctx.fillRect(startX, 0, widthSel, displayHeight);

            this.ctx.strokeStyle = selectionBorder;
            this.ctx.lineWidth = 2;
            this.ctx.strokeRect(startX + 0.5, 0.5, widthSel - 1, displayHeight - 1);

            // Selection times (top-left)
            this.ctx.font = '12px Inter, Arial, sans-serif';
            this.ctx.fillStyle = 'rgba(0,0,0,0.7)';
            const formatTime = (t) => {
                const s = Math.max(0, t || 0);
                const m = Math.floor(s / 60).toString().padStart(2, '0');
                const sec = Math.floor(s % 60).toString().padStart(2, '0');
                const ms = Math.floor((s % 1) * 1000).toString().padStart(3, '0');
                return `${m}:${sec}.${ms}`;
            };
            this.ctx.fillText(`${formatTime(this.selection_start)} → ${formatTime(this.selection_end)}`, startX + 8, 18);
        }

        // Playhead (single vertical line across full height)
        if (this.isPlaying) {
            const playX = (this.currentTime / this.audioBuffer.duration) * displayWidth - this.scrollPosition * displayWidth;
            this.ctx.beginPath();
            this.ctx.moveTo(playX, 0);
            this.ctx.lineTo(playX, displayHeight);
            this.ctx.lineWidth = 2;
            this.ctx.strokeStyle = '#D21E34';
            this.ctx.stroke();

            // small triangle marker at top
            this.ctx.beginPath();
            this.ctx.moveTo(playX - 6, 6);
            this.ctx.lineTo(playX + 6, 6);
            this.ctx.lineTo(playX, 16);
            this.ctx.closePath();
            this.ctx.fillStyle = '#D21E34';
            this.ctx.fill();
        }
    }

    handleMouseDown(e) {
        if (!this.audioBuffer) return;
        this.canvas.focus();
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const time = (x / rect.width + this.scrollPosition) * this.audioBuffer.duration;

        this.selection_start = time;
        this.selection_end = time;
        this.isSelecting = true;
        this.lastClickTime = time; // Sauvegarder la position cliquée
        this.drawWaveform();
    }

    handleMouseMove(e) {
        if (!this.isSelecting || !this.audioBuffer) return;

        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const time = (x / rect.width + this.scrollPosition) * this.audioBuffer.duration;

        this.selection_end = Math.max(0, Math.min(this.audioBuffer.duration, time));
        this.drawWaveform();
    }

    handleMouseUp() {
        if (!this.audioBuffer) return;

        // Si c'est un simple clic (pas de sélection étendue), sauter à la position cliquée
        if (this.selection_start === this.selection_end && this.lastClickTime !== undefined) {
            this.currentTime = this.lastClickTime;
            this.drawWaveform();
        }

        this.isSelecting = false;
    }

    handleWheel(e) {
        if (!this.audioBuffer) return;

        // Shift + mouse wheel (or a horizontal trackpad gesture) pans the
        // visible part of the waveform without using any extra control.
        if (e.shiftKey || e.deltaX !== 0) {
            e.preventDefault();
            const delta = e.deltaX || e.deltaY;
            this.scrollWaveform(Math.sign(delta) * (0.08 / this.zoom));
            return;
        }

        // Keep zooming available directly on the waveform with Ctrl/Cmd + wheel.
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            if (e.deltaY > 0) {
                this.zoomOut();
            } else {
                this.zoomIn();
            }
        }
    }

    zoomIn() {
        this.zoom = Math.min(this.zoom * 1.2, 10);
        this.scrollPosition = Math.min(this.scrollPosition, this.getMaxScrollPosition());
        this.drawWaveform();
    }

    zoomOut() {
        this.zoom = Math.max(this.zoom / 1.2, 1);
        this.scrollPosition = Math.min(this.scrollPosition, this.getMaxScrollPosition());
        this.drawWaveform();
    }

    fitToView() {
        this.zoom = 1;
        this.scrollPosition = 0;
        this.drawWaveform();
    }

    getMaxScrollPosition() {
        return Math.max(0, 1 - (1 / Math.max(1, this.zoom)));
    }

    scrollWaveform(amount) {
        this.scrollPosition = Math.max(
            0,
            Math.min(this.getMaxScrollPosition(), this.scrollPosition + amount)
        );
        this.drawWaveform();
    }

    selectAll() {
        if (!this.audioBuffer) return;
        this.selection_start = 0;
        this.selection_end = this.audioBuffer.duration;
        this.canvas.focus();
        this.drawWaveform();
    }

    clearSelection() {
        this.selection_start = 0;
        this.selection_end = 0;
        this.drawWaveform();
    }

    extendSelectionLeft() {
        if (!this.audioBuffer) return;

        // Définir le pas de sélection (en secondes)
        const step = 0.1; // 100ms par appui

        // Si pas de sélection, commencer une nouvelle sélection
        if (this.selection_start === this.selection_end) {
            this.selection_start = Math.max(0, this.currentTime - step);
            this.selection_end = this.currentTime;
        } else {
            // Sinon, étendre la sélection vers la gauche
            const minSelection = Math.min(this.selection_start, this.selection_end);
            this.selection_start = Math.max(0, minSelection - step);
        }

        this.drawWaveform();
    }

    extendSelectionRight() {
        if (!this.audioBuffer) return;

        // Définir le pas de sélection (en secondes)
        const step = 0.1; // 100ms par appui

        // Si pas de sélection, commencer une nouvelle sélection
        if (this.selection_start === this.selection_end) {
            this.selection_start = this.currentTime;
            this.selection_end = Math.min(this.audioBuffer.duration, this.currentTime + step);
        } else {
            // Sinon, étendre la sélection vers la droite
            const maxSelection = Math.max(this.selection_start, this.selection_end);
            this.selection_end = Math.min(this.audioBuffer.duration, maxSelection + step);
        }

        this.drawWaveform();
    }

    async playSelection() {
        if (!this.audioBuffer) return;

        const startTime = Math.min(this.selection_start, this.selection_end);
        const endTime = Math.max(this.selection_start, this.selection_end);
        const duration = endTime - startTime;

        if (duration === 0) return;

        this.stopPlayback();

        const source = this.audioContext.createBufferSource();
        source.buffer = this.audioBuffer;

        // Create gain node for selection playback
        const gainNode = this.audioContext.createGain();
        source.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        source.start(0, startTime, duration);
        this.isPlaying = true;
        this.currentTime = startTime;
        this.playbackSource = source;

        // Update live time display
        this.liveTimeUpdateInterval = setInterval(() => this.updateLiveTimeDisplay(), 100);

        this.drawWaveform();

        source.onended = () => {
            if (this.loopMode) {
                this.playSelection();
            } else {
                this.stopPlayback();
            }
        };
    }

    async playFromStart() {
        if (!this.audioBuffer) return;

        this.stopPlayback();

        const source = this.audioContext.createBufferSource();
        source.buffer = this.audioBuffer;
        source.connect(this.audioContext.destination);

        // Playback VU monitoring for buffer source
        try {
            const splitter = this.audioContext.createChannelSplitter(2);
            const leftAn = this.audioContext.createAnalyser();
            const rightAn = this.audioContext.createAnalyser();
            leftAn.fftSize = rightAn.fftSize = 2048;
            source.connect(splitter);
            splitter.connect(leftAn, 0);
            splitter.connect(rightAn, 1);

            this._playbackVUMonitor = {
                leftAn,
                rightAn,
                leftData: new Uint8Array(leftAn.frequencyBinCount),
                rightData: new Uint8Array(rightAn.frequencyBinCount),
                raf: null
            };

            const drawVUs = () => {
                if (!this._playbackVUMonitor) return;
                this._playbackVUMonitor.leftAn.getByteTimeDomainData(this._playbackVUMonitor.leftData);
                this._playbackVUMonitor.rightAn.getByteTimeDomainData(this._playbackVUMonitor.rightData);
                updateVUMeter(this._playbackVUMonitor.leftData, this._playbackVUMonitor.rightData);
                this._playbackVUMonitor.raf = requestAnimationFrame(drawVUs);
            };
            drawVUs();
        } catch (err) {
            console.warn('Playback VU monitor failed:', err);
        }

        source.start();
        this.isPlaying = true;
        this.currentTime = 0;
        this.playbackSource = source;

        // Update live time display
        this.liveTimeUpdateInterval = setInterval(() => this.updateLiveTimeDisplay(), 100);

        this.drawWaveform();

        source.onended = () => {
            if (this.loopMode) {
                this.playFromStart();
            } else {
                this.stopPlayback();
            }
        };
    }

    stopPlayback() {
        if (this.playbackSource) {
            try {
                this.playbackSource.stop();
            } catch (err) {
                console.warn('Playback already stopped:', err);
            }
            this.playbackSource.disconnect();
            this.playbackSource = null;
        }

        // Stop/cleanup any playback VU monitor
        if (this._playbackVUMonitor) {
            try { cancelAnimationFrame(this._playbackVUMonitor.raf); } catch (e) { }
            try { this._playbackVUMonitor.leftAn.disconnect(); this._playbackVUMonitor.rightAn.disconnect(); } catch (e) { }
            this._playbackVUMonitor = null;
            // reset VU to minimum
            const zeroLeft = new Uint8Array(2048 / 2).fill(128);
            const zeroRight = new Uint8Array(2048 / 2).fill(128);
            updateVUMeter(zeroLeft, zeroRight);
        }

        this.isPlaying = false;
        this.clearLiveTimeUpdate();
        // Mettre à jour currentTime avec la position actuelle avant d'arrêter
        // updateLiveTimeDisplay a déjà fait cela en continu, donc currentTime est à jour
        this.drawWaveform();
    }

    togglePlayPause() {
        if (!this.audioBuffer) return;

        if (this.isPlaying) {
            // Si la musique joue, mettre en pause
            this.stopPlayback();
            const btn = document.getElementById('playStopBtn');
            btn.classList.remove('btn-success');
            btn.classList.add('btn-outline-success');
            btn.querySelector('i').className = 'fas fa-play';
        } else {
            // Si la musique ne joue pas, commencer la lecture à partir de la position actuelle
            this.playFromCurrentTime();
            const btn = document.getElementById('playStopBtn');
            btn.classList.remove('btn-outline-success');
            btn.classList.add('btn-success');
            btn.querySelector('i').className = 'fas fa-pause';
        }
    }

    togglePlayStop() {
        if (!this.audioBuffer) return;

        if (this.isPlaying) {
            // Si la musique joue, arrêter et revenir au début
            this.stopPlayback();
            this.currentTime = 0;
            this.drawWaveform();
            const btn = document.getElementById('playStopBtn');
            btn.classList.remove('btn-success');
            btn.classList.add('btn-outline-success');
            btn.querySelector('i').className = 'fas fa-play';
        } else {
            // Si la musique ne joue pas, commencer la lecture à partir du début
            this.playFromStart();
            const btn = document.getElementById('playStopBtn');
            btn.classList.remove('btn-outline-success');
            btn.classList.add('btn-success');
            btn.querySelector('i').className = 'fas fa-stop';
        }
    }

    async toggleRecordStop() {
        if (!this.isRecording) {
            // Démarrer l'enregistrement
            await this.startRecording();
        } else {
            // Arrêter l'enregistrement
            await this.stopRecording();
        }
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 2,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false
                }
            });

            // Ensure editor has an AudioContext for constructing AudioBuffer from live PCM
            if (!this.audioContext) this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Prepare PCM capture buffers
            const _recSampleRate = this.audioContext.sampleRate;
            const _recLeftChunks = [];
            const _recRightChunks = [];
            let _recTotalSamples = 0;
            let _recProcessor = null;

            // Create a MediaStream source for live capture
            const src = this.audioContext.createMediaStreamSource(stream);
            try {
                const bufferSize = 4096;
                _recProcessor = this.audioContext.createScriptProcessor(bufferSize, 2, 2);
                src.connect(_recProcessor);
                try { _recProcessor.connect(this.audioContext.destination); } catch (e) { }
                _recProcessor.onaudioprocess = (e) => {
                    const inL = e.inputBuffer.getChannelData(0);
                    const inR = e.inputBuffer.numberOfChannels > 1 ? e.inputBuffer.getChannelData(1) : inL;
                    _recLeftChunks.push(new Float32Array(inL));
                    _recRightChunks.push(new Float32Array(inR));
                    _recTotalSamples += inL.length;

                    // Optional: update a lightweight preview buffer for the editor while recording
                    if (_recTotalSamples > 2048 && !_recProcessor._previewThrottle) {
                        _recProcessor._previewThrottle = true;
                        setTimeout(() => { _recProcessor._previewThrottle = false; }, 120);
                        try {
                            const previewLen = Math.min(_recTotalSamples, 32768);
                            const previewBuf = this.audioContext.createBuffer(2, previewLen, _recSampleRate);
                            const outL = previewBuf.getChannelData(0);
                            const outR = previewBuf.getChannelData(1);
                            let off = 0;
                            for (let i = Math.max(0, _recLeftChunks.length - 16); i < _recLeftChunks.length; i++) {
                                const c = _recLeftChunks[i];
                                outL.set(c, off);
                                outR.set(_recRightChunks[i], off);
                                off += c.length;
                                if (off >= previewLen) break;
                            }
                            this.audioBuffer = previewBuf;
                        } catch (e) {
                            // ignore preview errors
                        }
                    }
                };
            } catch (err) {
                console.warn('Realtime PCM capture not available inside AudioEditor.startRecording:', err);
            }

            this.mediaRecorder = new MediaRecorder(stream);
            this.recordedChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.recordedChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                // Prefer PCM-assembled buffer (from ScriptProcessor) to guarantee visual parity with live view
                try {
                    if (_recTotalSamples > 0) {
                        const finalBuf = this.audioContext.createBuffer(2, _recTotalSamples, _recSampleRate);
                        const outL = finalBuf.getChannelData(0);
                        const outR = finalBuf.getChannelData(1);
                        let off = 0;
                        for (let i = 0; i < _recLeftChunks.length; i++) {
                            outL.set(_recLeftChunks[i], off);
                            outR.set(_recRightChunks[i], off);
                            off += _recLeftChunks[i].length;
                        }
                        this.audioBuffer = finalBuf;
                    } else {
                        // fallback to decoding recorded blob
                        const blob = new Blob(this.recordedChunks, { type: 'audio/webm' });
                        const arrayBuffer = await blob.arrayBuffer();
                        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                        this.audioBuffer = audioBuffer;
                    }
                } catch (err) {
                    console.warn('Error assembling AudioBuffer from PCM chunks, falling back to decode:', err);
                    try {
                        const blob = new Blob(this.recordedChunks, { type: 'audio/webm' });
                        const arrayBuffer = await blob.arrayBuffer();
                        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                        this.audioBuffer = audioBuffer;
                    } catch (e) {
                        console.error('Decode fallback failed:', e);
                    }
                }

                this.currentTime = 0;
                this.selection_start = 0;
                this.selection_end = 0;
                this.drawWaveform();

                // cleanup
                try { if (_recProcessor) { _recProcessor.disconnect(); _recProcessor.onaudioprocess = null; } } catch (e) { }

                // Stop the stream tracks
                stream.getTracks().forEach(track => track.stop());
            };

            this.mediaRecorder.start();
            this.isRecording = true;

            // Désactiver Enregistrer, activer Arrêter
            document.getElementById('recordBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
        } catch (err) {
            console.error('Erreur lors du démarrage de l\'enregistrement:', err);
            alert('Impossible d\'accéder au microphone');
        }
    }

    async stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;

            // Désactiver Arrêter et réactiver Enregistrer
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('recordBtn').disabled = false;
        }
    }

    goToStart() {
        if (!this.audioBuffer) return;
        this.stopPlayback();
        this.currentTime = 0;
        this.drawWaveform();
    }

    goToEnd() {
        if (!this.audioBuffer) return;
        this.stopPlayback();
        this.currentTime = this.audioBuffer.duration;
        this.drawWaveform();
    }

    rewind() {
        if (!this.audioBuffer) return;
        const step = 10; // 10 seconds
        this.currentTime = Math.max(0, this.currentTime - step);
        this.updateLiveTimeDisplay();
        this.drawWaveform();
        // Jouer l'audio à partir de la nouvelle position
        this.playFromCurrentTime();
    }

    fastForward() {
        if (!this.audioBuffer) return;
        const step = 10; // 10 seconds
        this.currentTime = Math.min(this.audioBuffer.duration, this.currentTime + step);
        this.updateLiveTimeDisplay();
        this.drawWaveform();
        // Jouer l'audio à partir de la nouvelle position
        this.playFromCurrentTime();
    }

    playFromCurrentTime() {
        if (!this.audioBuffer) return;

        // Only stop if currently playing to avoid double-stopping
        if (this.isPlaying) {
            this.stopPlayback();
        } else {
            // If not playing, just clear any existing source
            if (this.playbackSource) {
                try {
                    this.playbackSource.stop();
                } catch (err) {
                    // Already stopped
                }
                this.playbackSource.disconnect();
                this.playbackSource = null;
            }
            this.clearLiveTimeUpdate();
        }

        const source = this.audioContext.createBufferSource();
        source.buffer = this.audioBuffer;
        source.connect(this.audioContext.destination);

        // Playback VU monitoring for buffer source
        try {
            const splitter = this.audioContext.createChannelSplitter(2);
            const leftAn = this.audioContext.createAnalyser();
            const rightAn = this.audioContext.createAnalyser();
            leftAn.fftSize = rightAn.fftSize = 2048;
            source.connect(splitter);
            splitter.connect(leftAn, 0);
            splitter.connect(rightAn, 1);

            this._playbackVUMonitor = {
                leftAn,
                rightAn,
                leftData: new Uint8Array(leftAn.frequencyBinCount),
                rightData: new Uint8Array(rightAn.frequencyBinCount),
                raf: null
            };

            const drawVUs = () => {
                if (!this._playbackVUMonitor) return;
                this._playbackVUMonitor.leftAn.getByteTimeDomainData(this._playbackVUMonitor.leftData);
                this._playbackVUMonitor.rightAn.getByteTimeDomainData(this._playbackVUMonitor.rightData);
                updateVUMeter(this._playbackVUMonitor.leftData, this._playbackVUMonitor.rightData);
                this._playbackVUMonitor.raf = requestAnimationFrame(drawVUs);
            };
            drawVUs();
        } catch (err) {
            console.warn('Playback VU monitor failed:', err);
        }

        const remainingDuration = this.audioBuffer.duration - this.currentTime;
        source.start(0, this.currentTime, remainingDuration);
        this.isPlaying = true;
        this.playbackSource = source;

        // Update live time display
        this.liveTimeUpdateInterval = setInterval(() => this.updateLiveTimeDisplay(), 100);

        this.drawWaveform();

        source.onended = () => {
            if (this.loopMode) {
                this.playFromStart();
            } else {
                this.stopPlayback();
            }
        };
    }

    toggleLoopMode() {
        this.loopMode = !this.loopMode;
        const loopBtn = document.getElementById('playLoopBtn');
        if (this.loopMode) {
            loopBtn.classList.remove('btn-outline-success');
            loopBtn.classList.add('btn-success');

            // Si la musique n'est pas en cours de lecture, démarrer la lecture
            if (!this.isPlaying && this.audioBuffer) {
                this.playFromStart();
            }
        } else {
            loopBtn.classList.remove('btn-success');
            loopBtn.classList.add('btn-outline-success');
        }
    }

    updateLiveTimeDisplay() {
        const timeDisplay = document.getElementById('liveTimeDisplay');

        // Incrémenter le temps de lecture si la musique joue
        if (this.isPlaying && this.audioBuffer) {
            this.currentTime += 0.1; // Ajouter 0.1 seconde (100ms)

            // S'assurer que le temps ne dépasse pas la durée totale
            if (this.currentTime > this.audioBuffer.duration) {
                this.currentTime = this.audioBuffer.duration;
            }
        }

        if (timeDisplay) {
            const minutes = Math.floor(this.currentTime / 60);
            const seconds = Math.floor(this.currentTime % 60);
            timeDisplay.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }

        // Redessiner le waveform pour montrer la ligne rouge de position de lecture
        this.drawWaveform();
    }

    clearLiveTimeUpdate() {
        if (this.liveTimeUpdateInterval) {
            clearInterval(this.liveTimeUpdateInterval);
            this.liveTimeUpdateInterval = null;
        }
    }

    cut() {
        if (!this.audioBuffer || this.selection_start === this.selection_end) return;

        const { startSample, endSample } = AudioUtils.getSelectionSampleRange(
            this.audioBuffer, this.selection_start, this.selection_end
        );

        this.clipboard = AudioUtils.createSubBuffer(this.audioContext, this.audioBuffer, startSample, endSample);
        document.getElementById('pasteBtn').disabled = false;
        this.deleteSelection();
    }

    copy() {
        if (!this.audioBuffer || this.selection_start === this.selection_end) return;

        const { startSample, endSample } = AudioUtils.getSelectionSampleRange(
            this.audioBuffer, this.selection_start, this.selection_end
        );

        this.clipboard = AudioUtils.createSubBuffer(this.audioContext, this.audioBuffer, startSample, endSample);
        document.getElementById('pasteBtn').disabled = false;
    }

    paste() {
        if (!this.audioBuffer || !this.clipboard) return;

        const insertPosition = Math.min(this.selection_start, this.selection_end);
        const insertSample = Math.floor(insertPosition * this.audioBuffer.sampleRate);

        this.audioBuffer = AudioUtils.insertBuffer(
            this.audioContext, this.audioBuffer, this.clipboard, insertSample
        );
        this.saveToHistory();
        this.updateAudioProperties();
        this.drawWaveform();
    }

    trim() {
        if (!this.audioBuffer || this.selection_start === this.selection_end) return;

        const { startSample, endSample } = AudioUtils.getSelectionSampleRange(
            this.audioBuffer, this.selection_start, this.selection_end
        );

        this.audioBuffer = AudioUtils.createSubBuffer(
            this.audioContext, this.audioBuffer, startSample, endSample
        );
        this.selection_start = 0;
        this.selection_end = this.audioBuffer.duration;
        this.saveToHistory();
        this.updateAudioProperties();
        this.drawWaveform();
    }

    delete() {
        if (!this.audioBuffer) return;
        if (this.selection_start === this.selection_end) {
            console.warn('Aucune sélection pour supprimer');
            return;
        }
        this.deleteSelection();
    }

    deleteSelection() {
        if (!this.audioBuffer || this.selection_start === this.selection_end) return;

        const { startTime, startSample, endSample } = AudioUtils.getSelectionSampleRange(
            this.audioBuffer, this.selection_start, this.selection_end
        );

        const updatedBuffer = AudioUtils.removeRange(
            this.audioContext, this.audioBuffer, startSample, endSample
        );

        if (updatedBuffer === null) {
            // Si tout l'audio a été supprimé, réinitialiser proprement l'éditeur
            this.clearAudio();
            return;
        }

        // Sinon, appliquer le nouveau buffer et ajuster la sélection
        this.audioBuffer = updatedBuffer;
        this.selection_start = startTime;
        this.selection_end = startTime;
        this.saveToHistory();
        this.updateAudioProperties();
        this.drawWaveform();
    }

    fadeIn() {
        if (!this.audioBuffer || this.selection_start === this.selection_end) return;

        const { startSample, endSample } = AudioUtils.getSelectionSampleRange(
            this.audioBuffer, this.selection_start, this.selection_end
        );

        for (let channel = 0; channel < this.audioBuffer.numberOfChannels; channel++) {
            const data = this.audioBuffer.getChannelData(channel);
            for (let i = startSample; i < endSample; i++) {
                const fadePosition = (i - startSample) / (endSample - startSample);
                data[i] *= fadePosition;
            }
        }

        this.saveToHistory();
        this.drawWaveform();
    }

    fadeOut() {
        if (!this.audioBuffer || this.selection_start === this.selection_end) return;

        const { startSample, endSample } = AudioUtils.getSelectionSampleRange(
            this.audioBuffer, this.selection_start, this.selection_end
        );

        for (let channel = 0; channel < this.audioBuffer.numberOfChannels; channel++) {
            const data = this.audioBuffer.getChannelData(channel);
            for (let i = startSample; i < endSample; i++) {
                const fadePosition = 1 - ((i - startSample) / (endSample - startSample));
                data[i] *= fadePosition;
            }
        }

        this.saveToHistory();
        this.drawWaveform();
    }

    normalize() {
        if (!this.audioBuffer) return;
        let maxAmplitude = 0;

        // Find maximum amplitude
        for (let channel = 0; channel < this.audioBuffer.numberOfChannels; channel++) {
            const data = this.audioBuffer.getChannelData(channel);
            for (let i = 0; i < data.length; i++) {
                maxAmplitude = Math.max(maxAmplitude, Math.abs(data[i]));
            }
        }

        if (maxAmplitude === 0) return;

        const normalizeFactor = 1 / maxAmplitude;

        // Apply normalization
        for (let channel = 0; channel < this.audioBuffer.numberOfChannels; channel++) {
            const data = this.audioBuffer.getChannelData(channel);
            for (let i = 0; i < data.length; i++) {
                data[i] *= normalizeFactor;
            }
        }

        this.saveToHistory();
        this.drawWaveform();
    }

    amplify(gainDb) {
        document.getElementById('amplifyValue').textContent = `${gainDb.toFixed(1)} dB`;
        if (!this.audioBuffer) return;

        const deltaDb = gainDb - this.lastAmplifyValue;
        if (Math.abs(deltaDb) < 0.01) {
            return;
        }

        const gain = Math.pow(10, deltaDb / 20);
        const hasSelection = this.selection_start !== this.selection_end;
        const startSample = hasSelection ? Math.floor(Math.min(this.selection_start, this.selection_end) * this.audioBuffer.sampleRate) : 0;
        const endSample = hasSelection ? Math.floor(Math.max(this.selection_start, this.selection_end) * this.audioBuffer.sampleRate) : this.audioBuffer.length;

        for (let channel = 0; channel < this.audioBuffer.numberOfChannels; channel++) {
            const data = this.audioBuffer.getChannelData(channel);
            for (let i = startSample; i < endSample; i++) {
                data[i] *= gain;
            }
        }

        this.lastAmplifyValue = gainDb;
        this.saveToHistory();
        this.drawWaveform();
    }

    saveToHistory(markDirty = true) {
        if (!this.audioBuffer || !this.audioContext) return;
        // Remove any history after current index
        this.history = this.history.slice(0, this.historyIndex + 1);

        const clonedBuffer = this.cloneBuffer(this.audioBuffer);

        this.history.push(clonedBuffer);
        this.historyIndex++;

        document.getElementById('undoBtn').disabled = this.historyIndex <= 0;
        document.getElementById('redoBtn').disabled = this.historyIndex >= this.history.length - 1;

        if (markDirty) {
            this.isDirty = true;
        }

        // Limit history to 50 states
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this.audioBuffer = this.cloneBuffer(this.history[this.historyIndex]);
            this.updateAudioProperties();
            this.drawWaveform();
        }

        const undoDisabled = this.historyIndex === 0;
        const redoDisabled = this.historyIndex >= this.history.length - 1;
        document.getElementById('undoBtn').disabled = undoDisabled;
        document.getElementById('redoBtn').disabled = redoDisabled;
        this.isDirty = !undoDisabled;
    }

    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            this.audioBuffer = this.cloneBuffer(this.history[this.historyIndex]);
            this.updateAudioProperties();
            this.drawWaveform();
        }

        const undoDisabled = this.historyIndex === 0;
        const redoDisabled = this.historyIndex >= this.history.length - 1;
        document.getElementById('undoBtn').disabled = undoDisabled;
        document.getElementById('redoBtn').disabled = redoDisabled;
        this.isDirty = !undoDisabled;
    }

    cloneBuffer(buffer) {
        return AudioUtils.cloneBuffer(this.audioContext, buffer);
    }

    exportAudio() {
        // Convert AudioBuffer to WAV Blob
        return AudioUtils.audioBufferToWav(this.audioBuffer);
    }

    hasEdits() {
        return !!this.audioBuffer && this.audioBuffer.length > 0 && this.isDirty;
    }

}

// Initialize audio editor
window.audioEditor = new AudioEditor();

const originalForm = document.getElementById('audioForm');

originalForm?.addEventListener('submit', function (e) {
    if (window.audioEditor?.hasEdits()) {
        e.preventDefault();

        const editedBlob = window.audioEditor.exportAudio();
        const editedFile = new File([editedBlob], `edited_audio_${Date.now()}.wav`, { type: 'audio/wav' });
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(editedFile);

        // Récupération et affectation sécurisée
        const inputEl = document.querySelector('input[type="file"]');
        if (inputEl) inputEl.files = dataTransfer.files;

        // Mise à jour de l'affichage
        const fileNameEl = document.getElementById('fileName');
        const fileSizeEl = document.getElementById('fileSize');
        const fileInfoEl = document.getElementById('fileInfo');

        if (fileNameEl) fileNameEl.textContent = editedFile.name;
        if (fileSizeEl) fileSizeEl.textContent = (editedFile.size / 1024).toFixed(2) + ' KB';
        fileInfoEl?.classList.add('show');

        setTimeout(() => {
            originalForm.submit();
        }, 50);
    }
});
