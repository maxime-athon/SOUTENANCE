// add_audio.js le script pour la page d'ajout d'audio
// explication: ce script gère l'upload de fichiers audio, 
// la validation des champs du formulaire, l'affichage d'un aperçu des informations saisies, et la gestion de la progression de l'upload.
//  Il inclut également la gestion des événements de drag-and-drop pour le fichier audio et l'intégration avec un éditeur audio si disponible.

(function () {
    'use strict';

    const MAX_FILE_SIZE = 100 * 1024 * 1024;
    const DURATION_PATTERN = /^(\d{1,2}):([0-5]\d):([0-5]\d)$/;

    // File upload functionality
    const fileInput = document.querySelector('input[type="file"]');
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const audioPreview = document.getElementById('audioPreview');
    const form = document.getElementById('audioForm');
    const formFeedback = document.getElementById('formFeedback');
    const submitBtn = document.getElementById('submitBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadProgressBar = document.getElementById('uploadProgressBar');
    const uploadProgressBarWrap = document.getElementById('uploadProgressBarWrap');
    const uploadProgressPercent = document.getElementById('uploadProgressPercent');
    const uploadProgressLabel = document.getElementById('uploadProgressLabel');

    const validationRules = {
        title: { el: () => document.querySelector('input[name="title"]'), errorId: 'titleError', successId: 'titleSuccess', validate: (v) => v.trim().length >= 2, message: 'Le titre doit contenir au moins 2 caractères.' },
        category: { el: () => document.querySelector('select[name="category"]'), errorId: 'categoryError', validate: (v) => v !== '', message: 'Veuillez sélectionner une catégorie.' },
        producer: { el: () => document.querySelector('input[name="producer"]'), errorId: 'producerError', validate: (v) => v.trim().length >= 2, message: 'Indiquez le producteur ou réalisateur.' },
        recording_date: { el: () => document.querySelector('input[name="recording_date"]'), errorId: 'recordingDateError', validate: (v) => v !== '', message: 'La date d\'enregistrement est obligatoire.' },
        broadcast_date: { el: () => document.querySelector('input[name="broadcast_date"]'), errorId: 'broadcastDateError', validate: (v) => v !== '', message: 'La date de diffusion est obligatoire.' },
        duration: { el: () => document.querySelector('input[name="duration"]'), errorId: 'durationError', successId: 'durationSuccess', validate: (v) => !v.trim() || DURATION_PATTERN.test(v.trim()), message: 'Utilisez le format HH:MM:SS (ex. 01:23:45).' },
    };

    function setFieldState(field, isValid, message) {
        const input = validationRules[field]?.el();
        if (!input) return isValid;
        const rule = validationRules[field];
        const errorEl = document.getElementById(rule.errorId);
        const successEl = rule.successId ? document.getElementById(rule.successId) : null;

        input.classList.remove('is-valid', 'is-invalid');
        input.setAttribute('aria-invalid', isValid ? 'false' : 'true');

        if (errorEl) {
            errorEl.textContent = isValid ? '' : message;
            errorEl.style.display = isValid ? 'none' : 'block';
        }
        if (successEl) {
            successEl.style.display = isValid && input.value.trim() ? 'block' : 'none';
        }

        if (!isValid) {
            input.classList.add('is-invalid');
        } else if (input.value.trim()) {
            input.classList.add('is-valid');
        }
        return isValid;
    }

    function validateField(field) {
        const rule = validationRules[field];
        if (!rule) return true;
        const input = rule.el();
        if (!input) return true;
        return setFieldState(field, rule.validate(input.value), rule.message);
    }

    function validateFile() {
        const fileError = document.getElementById('fileError');
        const file = fileInput?.files?.[0];
        if (!file) {
            if (fileError) {
                fileError.textContent = 'Veuillez sélectionner un fichier audio.';
                fileError.style.display = 'block';
            }
            fileUploadArea?.classList.add('is-invalid');
            fileUploadArea?.setAttribute('aria-invalid', 'true');
            return false;
        }
        if (!isAudioFile(file)) {
            if (fileError) {
                fileError.textContent = 'Format non supporté. Utilisez MP3, WAV, OGG, AAC ou WebM.';
                fileError.style.display = 'block';
            }
            return false;
        }
        if (file.size > MAX_FILE_SIZE) {
            if (fileError) {
                fileError.textContent = 'Le fichier dépasse la limite de 100 Mo.';
                fileError.style.display = 'block';
            }
            return false;
        }
        if (fileError) {
            fileError.textContent = '';
            fileError.style.display = 'none';
        }
        fileUploadArea?.classList.remove('is-invalid');
        fileUploadArea?.setAttribute('aria-invalid', 'false');
        return true;
    }

    function validateForm() {
        let valid = true;
        Object.keys(validationRules).forEach((field) => {
            if (!validateField(field)) valid = false;
        });
        if (!validateFile()) valid = false;

        if (formFeedback) {
            formFeedback.classList.toggle('d-none', valid);
        }
        if (!valid && formFeedback) {
            formFeedback.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        return valid;
    }

    function showUploadProgress(label, percent) {
        if (!uploadProgress) return;
        uploadProgress.classList.remove('d-none');
        if (uploadProgressLabel) uploadProgressLabel.textContent = label;
        if (uploadProgressBar) uploadProgressBar.style.width = `${percent}%`;
        if (uploadProgressPercent) uploadProgressPercent.textContent = `${percent} %`;
        if (uploadProgressBarWrap) uploadProgressBarWrap.setAttribute('aria-valuenow', String(percent));
    }

    Object.keys(validationRules).forEach((field) => {
        const input = validationRules[field].el();
        if (input) {
            input.addEventListener('input', () => validateField(field));
            input.addEventListener('blur', () => validateField(field));
        }
    });

    if (fileUploadArea && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
            fileUploadArea.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach((eventName) => {
            fileUploadArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach((eventName) => {
            fileUploadArea.addEventListener(eventName, unhighlight, false);
        });

        fileUploadArea.addEventListener('drop', handleDrop, false);
        fileUploadArea.addEventListener('click', () => fileInput.click());
        fileUploadArea.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                fileInput.click();
            }
        });
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        fileUploadArea?.classList.add('dragover');
    }

    function unhighlight() {
        fileUploadArea?.classList.remove('dragover');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (typeof DataTransfer !== 'undefined') {
            const transfer = new DataTransfer();
            Array.from(files).forEach((file) => transfer.items.add(file));
            fileInput.files = transfer.files;
        } else {
            fileInput.files = files;
        }
        handleFileSelect();
        validateFile();
    }

    fileInput?.addEventListener('change', () => {
        handleFileSelect();
        validateFile();
    });

    function handleFileSelect(skipEditorLoad = false) {
        const skipLoad = skipEditorLoad === true;
        const file = fileInput.files[0];
        if (file) {
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            fileInfo.classList.add('show');
            updatePreview();
            if (isAudioFile(file)) {
                if (!skipLoad && window.audioEditor) {
                    window.audioEditor.loadAudioFromFile(file);
                }
            } else {
                const fileError = document.getElementById('fileError');
                if (fileError) {
                    fileError.textContent = 'Veuillez sélectionner un fichier audio valide (MP3, WAV, OGG, etc.).';
                    fileError.style.display = 'block';
                }
                fileInput.value = '';
                fileInfo.classList.remove('show');
                audioPreview.classList.remove('show');
                if (window.audioEditor) window.audioEditor.clearAudio();
                return;
            }
        } else {
            fileInfo.classList.remove('show');
            audioPreview.classList.remove('show');
            if (window.audioEditor) window.audioEditor.clearAudio();
        }
    }

    window.handleFileSelect = handleFileSelect;
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function isAudioFile(file) {
        if (!file) return false;
        if (file.type && file.type.startsWith('audio/')) return true;
        const extension = file.name ? file.name.split('.').pop() : '';
        return /\.(mp3|wav|ogg|m4a|aac|webm|flac)$/i.test(extension ? `.${extension}` : '');
    }

    // Form preview functionality
    if (form) {
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', updatePreview);
        });
    }

    function updatePreview() {
        const title = document.querySelector('input[name="title"]')?.value || '';
        const categorySelect = document.querySelector('select[name="category"]');
        const category = categorySelect && categorySelect.selectedIndex >= 0
            ? categorySelect.options[categorySelect.selectedIndex].textContent.trim()
            : '';
        const producer = document.querySelector('input[name="producer"]')?.value || '';
        const duration = document.querySelector('input[name="duration"]')?.value || '';
        const subtitle = document.querySelector('input[name="subtitle"]')?.value || '';
        const bandNumber = document.querySelector('input[name="band_number"]')?.value || '';
        const recordingNumber = document.querySelector('input[name="recording_number"]')?.value || '';
        const recordingDate = document.querySelector('input[name="recording_date"]')?.value || '';
        const speed = document.querySelector('input[name="speed"]')?.value || '';
        const broadcastDate = document.querySelector('input[name="broadcast_date"]')?.value || '';
        const previewFile = document.getElementById('previewFileName');

        const setPreview = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value.trim() ? value : '—';
        };

        setPreview('previewTitle', title);
        setPreview('previewCategory', category);
        setPreview('previewProducer', producer);
        setPreview('previewDuration', duration);
        if (previewFile) {
            previewFile.textContent = fileInput?.files?.[0]?.name || '—';
        }

        if (document.getElementById('previewSubtitle')) document.getElementById('previewSubtitle').textContent = subtitle || '—';
        if (document.getElementById('previewBandNumber')) document.getElementById('previewBandNumber').textContent = bandNumber || '—';
        if (document.getElementById('previewRecordingNumber')) document.getElementById('previewRecordingNumber').textContent = recordingNumber || '—';
        if (document.getElementById('previewRecordingDate')) document.getElementById('previewRecordingDate').textContent = recordingDate || '—';
        if (document.getElementById('previewSpeed')) document.getElementById('previewSpeed').textContent = speed || '—';
        if (document.getElementById('previewBroadcastDate')) document.getElementById('previewBroadcastDate').textContent = broadcastDate || '—';

        if (title || category || producer || duration) {
            audioPreview?.classList.add('show');
        } else {
            audioPreview?.classList.remove('show');
        }
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


    // Single Form Submission Handler
    function finalizeSubmit() {
        showUploadProgress('Archivage en cours…', 100);
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Envoi…';
        }
        form.submit();
    }

    if (form) {
        form.addEventListener('submit', function (e) {
            if (!validateForm()) {
                e.preventDefault();
                return;
            }

            showUploadProgress('Préparation du fichier…', 25);

            if (window.audioEditor && window.audioEditor.hasEdits()) {
                e.preventDefault();
                showUploadProgress('Export de l\'audio édité…', 60);

                const editedBlob = window.audioEditor.exportAudio();
                if (editedBlob) {
                    const editedFile = new File([editedBlob], `edited_audio_${Date.now()}.wav`, { type: 'audio/wav' });
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(editedFile);
                    fileInput.files = dataTransfer.files;

                    if (fileName) fileName.textContent = editedFile.name;
                    if (fileSize) fileSize.textContent = formatFileSize(editedFile.size);
                    fileInfo?.classList.add('show');
                    updatePreview();
                }

                setTimeout(finalizeSubmit, 50);
            } else {
                showUploadProgress('Transmission au serveur…', 75);
                if (submitBtn) submitBtn.disabled = true;
            }
        });
    }
})();
