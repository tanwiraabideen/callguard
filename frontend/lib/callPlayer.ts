// Plays a simulated call and sends the same audio to the backend as it plays.
// Both follow the audio clock, so the backend hears each moment as it is played.

import { AUDIO_SEND_INTERVAL_MS, BACKEND_URL } from "./config";

export type CallInfo = {
  id: string;
  title: string;
  duration_seconds: number;
  sample_rate: number;
};

export type EndReason = "finished" | "stopped" | "connection_lost";

// The browser decodes audio to numbers from -1 to 1. This converts them back to
// the original 16-bit whole numbers.
function toInt16(sample: number): number {
  return Math.max(-32768, Math.min(32767, Math.round(sample * 32768)));
}

// Packs a stretch of audio into the format the backend expects: 16-bit samples,
// with the caller then the user for each frame.
function toStereoPcm(audio: AudioBuffer, from: number, to: number): ArrayBuffer {
  const caller = audio.getChannelData(0);
  const user = audio.getChannelData(1);
  const pcm = new Int16Array((to - from) * 2);

  for (let frame = from; frame < to; frame++) {
    const index = (frame - from) * 2;
    pcm[index] = toInt16(caller[frame]);
    pcm[index + 1] = toInt16(user[frame]);
  }
  return pcm.buffer;
}

// Starts the call and returns a function that stops it early.
export async function playCall(
  call: CallInfo,
  socket: WebSocket,
  onPlayed: (seconds: number) => void,
  onEnded: (reason: EndReason) => void,
): Promise<() => void> {
  // Using the call's own sample rate means the browser doesn't resample it.
  const context = new AudioContext({ sampleRate: call.sample_rate });
  const response = await fetch(`${BACKEND_URL}/calls/${call.id}/audio`);
  const audio = await context.decodeAudioData(await response.arrayBuffer());

  // Each channel goes to both ears, so the caller isn't only in the left ear.
  const source = context.createBufferSource();
  const splitter = context.createChannelSplitter(2);
  source.buffer = audio;
  source.connect(splitter);
  splitter.connect(context.destination, 0);
  splitter.connect(context.destination, 1);

  socket.send(JSON.stringify({ type: "call_start", call_id: call.id }));

  const startTime = context.currentTime + 0.1;
  let framesSent = 0;
  let ended = false;

  function sendUpTo(frame: number) {
    if (frame > framesSent && socket.readyState === WebSocket.OPEN) {
      socket.send(toStereoPcm(audio, framesSent, frame));
      framesSent = frame;
    }
  }

  function playedFrames() {
    const played = Math.floor((context.currentTime - startTime) * audio.sampleRate);
    return Math.max(0, Math.min(played, audio.length));
  }

  function finish(reason: EndReason) {
    if (ended) return;
    ended = true;
    clearInterval(timer);
    // A call that played to the end sends any audio the last tick missed.
    sendUpTo(reason === "finished" ? audio.length : playedFrames());
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "call_end", reason }));
    }
    source.onended = null;
    source.stop();
    context.close();
    onEnded(reason);
  }

  const timer = setInterval(() => {
    if (socket.readyState !== WebSocket.OPEN) {
      finish("connection_lost");
      return;
    }
    sendUpTo(playedFrames());
    onPlayed(playedFrames() / audio.sampleRate);
  }, AUDIO_SEND_INTERVAL_MS);

  source.onended = () => finish("finished");
  source.start(startTime);

  return () => finish("stopped");
}
