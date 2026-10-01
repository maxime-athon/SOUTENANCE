/*
 * Fonctions pures et fonctions de rendu partagées par l'éditeur audio.
 * Ce fichier est chargé avant audio_editor.js (voir add_audio.html).
 */
window.AudioUtils = (() => {
    const formatTime = (time) => {
        const seconds = Math.max(0, time || 0);
        const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
        const remainder = Math.floor(seconds % 60).toString().padStart(2, '0');
        const milliseconds = Math.floor((seconds % 1) * 1000).toString().padStart(3, '0');
        return `${minutes}:${remainder}.${milliseconds}`;
    };

    const getSelectionSampleRange = (audioBuffer, selectionStart, selectionEnd) => {
        const startTime = Math.min(selectionStart, selectionEnd);
        const endTime = Math.max(selectionStart, selectionEnd);
        return {
            startTime,
            endTime,
            startSample: Math.floor(startTime * audioBuffer.sampleRate),
            endSample: Math.floor(endTime * audioBuffer.sampleRate),
        };
    };

    const createSubBuffer = (audioContext, audioBuffer, startSample, endSample) => {
        const newBuffer = audioContext.createBuffer(
            audioBuffer.numberOfChannels,
            endSample - startSample,
            audioBuffer.sampleRate
        );

        for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
            newBuffer.getChannelData(channel).set(
                audioBuffer.getChannelData(channel).subarray(startSample, endSample)
            );
        }
        return newBuffer;
    };

    const insertBuffer = (audioContext, originalBuffer, bufferToInsert, insertPosition) => {
        const newBuffer = audioContext.createBuffer(
            originalBuffer.numberOfChannels,
            originalBuffer.length + bufferToInsert.length,
            originalBuffer.sampleRate
        );

        for (let channel = 0; channel < originalBuffer.numberOfChannels; channel++) {
            const source = originalBuffer.getChannelData(channel);
            const target = newBuffer.getChannelData(channel);
            target.set(source.subarray(0, insertPosition));
            target.set(bufferToInsert.getChannelData(channel), insertPosition);
            target.set(source.subarray(insertPosition), insertPosition + bufferToInsert.length);
        }
        return newBuffer;
    };

    const removeRange = (audioContext, audioBuffer, startSample, endSample) => {
        if (!audioBuffer) return null;

        // Normalisation et sécurisation des bornes
        const totalSamples = audioBuffer.length;
        const start = Math.max(0, Math.min(startSample, totalSamples));
        const end = Math.max(start, Math.min(endSample, totalSamples));

        const samplesToRemove = end - start;

        // Si la plage à supprimer est vide ou invalide, on renvoie le buffer d'origine
        if (samplesToRemove <= 0) {
            return audioBuffer;
        }

        const newLength = totalSamples - samplesToRemove;

        // Si toute la piste est supprimée, on évite createBuffer avec 0 frame
        if (newLength <= 0) {
            return null;
        }

        // Création du nouveau buffer audio
        const newBuffer = audioContext.createBuffer(
            audioBuffer.numberOfChannels,
            newLength,
            audioBuffer.sampleRate
        );

        // Copie des segments audio restants
        for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
            const source = audioBuffer.getChannelData(channel);
            const target = newBuffer.getChannelData(channel);

            target.set(source.subarray(0, start));
            target.set(source.subarray(end), start);
        }

        return newBuffer;
    };

    const cloneBuffer = (audioContext, buffer) => {
        const clonedBuffer = audioContext.createBuffer(
            buffer.numberOfChannels,
            buffer.length,
            buffer.sampleRate
        );
        for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
            clonedBuffer.getChannelData(channel).set(buffer.getChannelData(channel));
        }
        return clonedBuffer;
    };

    const audioBufferToWav = (buffer) => {
        const bytesPerSample = 2;
        const blockAlign = buffer.numberOfChannels * bytesPerSample;
        const dataSize = buffer.length * blockAlign;
        const arrayBuffer = new ArrayBuffer(44 + dataSize);
        const view = new DataView(arrayBuffer);
        const writeString = (offset, value) => {
            for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
        };

        writeString(0, 'RIFF');
        view.setUint32(4, arrayBuffer.byteLength - 8, true);
        writeString(8, 'WAVE');
        writeString(12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, buffer.numberOfChannels, true);
        view.setUint32(24, buffer.sampleRate, true);
        view.setUint32(28, buffer.sampleRate * blockAlign, true);
        view.setUint16(32, blockAlign, true);
        view.setUint16(34, 16, true);
        writeString(36, 'data');
        view.setUint32(40, dataSize, true);

        let offset = 44;
        for (let sampleIndex = 0; sampleIndex < buffer.length; sampleIndex++) {
            for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
                const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[sampleIndex]));
                view.setInt16(offset, sample * 0x7FFF, true);
                offset += bytesPerSample;
            }
        }
        return new Blob([arrayBuffer], { type: 'audio/wav' });
    };

    const drawWaveform = (editor) => {
        const { canvas, ctx, audioBuffer } = editor;
        if (!canvas || !ctx) return;

        const rect = canvas.getBoundingClientRect();
        const width = Math.floor(rect.width);
        const height = Math.floor(rect.height);
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#f8f9fa';
        ctx.fillRect(0, 0, width, height);
        if (!audioBuffer || !width || !height) return;

        const drawChannel = (data, y, channelHeight, label) => {
            const centerY = y + channelHeight / 2;
            const samplesPerPixel = Math.max(1, Math.floor(data.length / (width * editor.zoom)));
            const scrollOffset = Math.floor(editor.scrollPosition * data.length);
            const minYs = new Array(width);
            const maxYs = new Array(width);
            const amplitude = (channelHeight / 2) - 2;

            for (let x = 0; x < width; x++) {
                let min = 1;
                let max = -1;
                const start = scrollOffset + Math.floor(x * samplesPerPixel);
                for (let sample = start; sample < start + samplesPerPixel && sample < data.length; sample++) {
                    const value = data[sample];
                    if (value < min) min = value;
                    if (value > max) max = value;
                }
                minYs[x] = centerY + min * amplitude;
                maxYs[x] = centerY + max * amplitude;
            }

            ctx.beginPath();
            ctx.moveTo(0, minYs[0] || centerY);
            for (let x = 1; x < width; x++) ctx.lineTo(x, minYs[x]);
            for (let x = width - 1; x >= 0; x--) ctx.lineTo(x, maxYs[x]);
            ctx.closePath();
            const gradient = ctx.createLinearGradient(0, y, 0, y + channelHeight);
            gradient.addColorStop(0, 'rgba(34,90,64,0.14)');
            gradient.addColorStop(1, 'rgba(34,90,64,0.05)');
            ctx.fillStyle = gradient;
            ctx.fill();
            ctx.lineWidth = 1.2;
            ctx.strokeStyle = '#225A40';
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, centerY);
            ctx.lineTo(width, centerY);
            ctx.lineWidth = 1;
            ctx.strokeStyle = 'rgba(0,0,0,0.08)';
            ctx.stroke();
            ctx.font = '12px Inter, Arial, sans-serif';
            ctx.fillStyle = 'rgba(0,0,0,0.6)';
            ctx.fillText(label, 8, y + 14);
        };

        const leftData = audioBuffer.getChannelData(0);
        const rightData = audioBuffer.numberOfChannels > 1 ? audioBuffer.getChannelData(1) : leftData;
        if (audioBuffer.numberOfChannels > 1) {
            const half = Math.max(40, Math.floor((height - 8) / 2));
            drawChannel(leftData, 6, half - 6, 'Gauche');
            drawChannel(rightData, half + 8, half - 6, 'Droit');
        } else {
            drawChannel(leftData, 0, height, 'Mono');
        }

        if (editor.selection_start !== editor.selection_end) {
            const startX = Math.max(0, (editor.selection_start / audioBuffer.duration) * width - editor.scrollPosition * width);
            const endX = Math.min(width, (editor.selection_end / audioBuffer.duration) * width - editor.scrollPosition * width);
            const selectionWidth = Math.max(0, endX - startX);
            ctx.fillStyle = 'rgba(34,90,64,0.12)';
            ctx.fillRect(startX, 0, selectionWidth, height);
            ctx.strokeStyle = 'rgba(34,90,64,0.6)';
            ctx.lineWidth = 2;
            ctx.strokeRect(startX + 0.5, 0.5, selectionWidth - 1, height - 1);
            ctx.font = '12px Inter, Arial, sans-serif';
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.fillText(`${formatTime(editor.selection_start)} → ${formatTime(editor.selection_end)}`, startX + 8, 18);
        }

        if (editor.isPlaying) {
            const x = (editor.currentTime / audioBuffer.duration) * width - editor.scrollPosition * width;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#D21E34';
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(x - 6, 6);
            ctx.lineTo(x + 6, 6);
            ctx.lineTo(x, 16);
            ctx.closePath();
            ctx.fillStyle = '#D21E34';
            ctx.fill();
        }
    };

    return Object.freeze({
        formatTime,
        getSelectionSampleRange,
        createSubBuffer,
        insertBuffer,
        removeRange,
        cloneBuffer,
        audioBufferToWav,
        drawWaveform,
    });
})();
