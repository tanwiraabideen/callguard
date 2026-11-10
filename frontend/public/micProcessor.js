// Runs on the browser's audio thread. Collects microphone samples and hands them
// to the page in chunks of about 100 ms.

const CHUNK_SAMPLES = 1600;

class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(CHUNK_SAMPLES);
    this.filled = 0;
  }

  process(inputs) {
    const samples = inputs[0][0];
    if (!samples) return true;

    for (const sample of samples) {
      this.buffer[this.filled++] = sample;
      if (this.filled === CHUNK_SAMPLES) {
        this.port.postMessage(this.buffer.slice());
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
