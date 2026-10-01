/**
 * extraction.js - Service client d'extraction automatique de métadonnées audio
 * Radio Kara Archive Project
 */

// ==========================================
// FONCTIONS UTILITAIRES (Outer Scope / Portée externe)
// ==========================================

/**
 * Génère un titre propre basé sur le nom du fichier
 * @param {string} filename 
 * @returns {string}
 */
function generateCleanTitle(filename) {
    if (!filename) return '';
    const nameWithoutExt = filename.substring(0, filename.lastIndexOf('.')) || filename;
    const cleanName = nameWithoutExt.replace(/[-_]/g, ' ').replace(/\s+/g, ' ').trim();
    return cleanName.charAt(0).toUpperCase() + cleanName.slice(1);
}

/**
 * Convertit des secondes au format HH:MM:SS
 * @param {number} seconds 
 * @returns {string}
 */
function formatDuration(seconds) {
    const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
}

/**
 * Convertit des secondes au format MM:SS.mmm pour l'affichage précis
 * @param {number} seconds 
 * @returns {string}
 */
function formatDurationWithMs(seconds) {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    const ms = Math.floor((seconds % 1) * 1000).toString().padStart(3, '0');
    return `${m}:${s}.${ms}`;
}

/**
 * Analyse le fichier avec la Web Audio API
 * @param {File} file 
 * @param {Object} targets 
 */
function extractAudioContextData(file, targets) {
    const reader = new FileReader();

    reader.onload = function (e) {
        const arrayBuffer = e.target.result;
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;

        const audioCtx = new AudioContext();

        audioCtx.decodeAudioData(arrayBuffer, (audioBuffer) => {
            const totalSeconds = audioBuffer.duration;
            const sampleRate = audioBuffer.sampleRate;
            const numberOfChannels = audioBuffer.numberOfChannels;

            const bitrateKbps = (totalSeconds && totalSeconds > 0) ? Math.round((file.size * 8) / (totalSeconds * 1000)): 0;
            const formattedSpeed = `${bitrateKbps} kbps`;
            const formattedDuration = formatDuration(totalSeconds);

            if (targets.durationInput) {
                targets.durationInput.value = formattedDuration;
            }
            if (targets.speedInput) {
                targets.speedInput.value = formattedSpeed;
            }

            if (targets.propDuration) targets.propDuration.textContent = formatDurationWithMs(totalSeconds);
            if (targets.propSampleRate) targets.propSampleRate.textContent = `${sampleRate} Hz`;
            if (targets.propChannels) targets.propChannels.textContent = numberOfChannels === 1 ? '1 (Mono)' : `${numberOfChannels} (Stéréo)`;
            if (targets.previewDuration) targets.previewDuration.textContent = formattedDuration;
            if (targets.previewSpeed) targets.previewSpeed.textContent = formattedSpeed;

            audioCtx.close();
        }, (err) => {
            audioCtx.close();
            fallbackAudioExtraction(file, targets);
        });
    };

    reader.readAsArrayBuffer(file);
}

/**
 * Méthode de secours via l'élément Audio HTML5
 * @param {File} file 
 * @param {Object} targets 
 */
function fallbackAudioExtraction(file, targets) {
    const tempAudio = new Audio();
    tempAudio.src = URL.createObjectURL(file);

    tempAudio.onloadedmetadata = function () {
        const totalSeconds = tempAudio.duration;
        const formattedDuration = formatDuration(totalSeconds);
        const bitrateKbps = Math.round((file.size * 8) / (totalSeconds * 1000));
        const formattedSpeed = `${bitrateKbps} kbps`;

        if (targets.durationInput) {
            targets.durationInput.value = formattedDuration;
        }
        if (targets.speedInput) {
            targets.speedInput.value = formattedSpeed;
        }

        if (targets.propDuration) targets.propDuration.textContent = formatDurationWithMs(totalSeconds);
        if (targets.previewDuration) targets.previewDuration.textContent = formattedDuration;
        if (targets.previewSpeed) targets.previewSpeed.textContent = formattedSpeed;

        URL.revokeObjectURL(tempAudio.src);
    };
}

// ==========================================
// ÉCOUTEUR D'ÉVÉNEMENT PRINCIPAL
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.querySelector('input[type="file"]');
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileNameDisplay = document.getElementById('fileName');
    const fileSizeDisplay = document.getElementById('fileSize');
    const fileInfoBox = document.getElementById('fileInfo');

    const titleInput = document.querySelector('input[name="title"]');
    const durationInput = document.querySelector('input[name="duration"]');
    const speedInput = document.querySelector('input[name="speed"]') || document.querySelector('select[name="speed"]');

    const propDuration = document.getElementById('audioDuration');
    const propSampleRate = document.getElementById('audioSampleRate');
    const propChannels = document.getElementById('audioChannels');
    const propFormat = document.getElementById('audioFormat');

    const previewTitle = document.getElementById('previewTitle');
    const previewDuration = document.getElementById('previewDuration');
    const previewSpeed = document.getElementById('previewSpeed');

    if (!fileInput) return;

    if (fileUploadArea) {
        fileUploadArea.addEventListener('click', (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });
    }

    fileInput.addEventListener('change', (event) => {
        const files = event.target.files;
        if (!files || files.length === 0) return;

        const file = files[0];

        if (fileNameDisplay) fileNameDisplay.textContent = file.name;
        if (fileSizeDisplay) fileSizeDisplay.textContent = `(${(file.size / (1024 * 1024)).toFixed(2)} Mo)`;
        if (fileInfoBox) fileInfoBox.classList.add('show');

        const cleanTitle = generateCleanTitle(file.name);
        if (titleInput) {
            titleInput.value = cleanTitle;
        }
        if (previewTitle) {
            previewTitle.textContent = cleanTitle;
        }

        const fileExt = file.name.substring(file.name.lastIndexOf('.') + 1).toUpperCase();
        if (propFormat) {
            propFormat.textContent = fileExt || file.type || 'Inconnu';
        }

        if (propDuration) propDuration.textContent = 'Analyse...';
        if (propSampleRate) propSampleRate.textContent = 'Analyse...';
        if (propChannels) propChannels.textContent = 'Analyse...';

        extractAudioContextData(file, {
            durationInput,
            speedInput,
            propDuration,
            propSampleRate,
            propChannels,
            previewDuration,
            previewSpeed
        });
    });
});

window.extractAudioContextData = extractAudioContextData;