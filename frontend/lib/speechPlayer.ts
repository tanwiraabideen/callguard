// Plays what the agent says, one item at a time, in the browser only. None of
// this is sent to the backend, so a whisper can never enter the call audio.

import { BROWSER_SPEECH_TIMEOUT_MS } from "./config";

export type SpeechMessage = {
  kind: "whisper" | "to_caller";
  text: string;
  audio_base64: string | null;
};

function decodeBase64(data: string): ArrayBuffer {
  const bytes = Uint8Array.from(atob(data), (char) => char.charCodeAt(0));
  return bytes.buffer;
}

export class SpeechPlayer {
  private context = new AudioContext();
  private queue: Promise<void> = Promise.resolve();

  constructor(
    private onStart: () => void,
    private onFinish: () => void,
  ) {}

  enqueue(message: SpeechMessage) {
    this.queue = this.queue.then(() => this.play(message)).catch(console.error);
  }

  // Resolves once everything queued so far has been spoken.
  whenIdle(): Promise<void> {
    return this.queue;
  }

  close() {
    window.speechSynthesis.cancel();
    this.context.close();
  }

  private async play(message: SpeechMessage) {
    this.onStart();
    try {
      if (message.audio_base64) {
        await this.playAudio(message.audio_base64);
      } else {
        await this.speakWithBrowserVoice(message.text);
      }
    } finally {
      this.onFinish();
    }
  }

  private async playAudio(data: string) {
    const audio = await this.context.decodeAudioData(decodeBase64(data));
    const source = this.context.createBufferSource();
    source.buffer = audio;
    source.connect(this.context.destination);
    await new Promise<void>((resolve) => {
      source.onended = () => resolve();
      source.start();
    });
  }

  private speakWithBrowserVoice(text: string) {
    return new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
      setTimeout(resolve, BROWSER_SPEECH_TIMEOUT_MS);
    });
  }
}
