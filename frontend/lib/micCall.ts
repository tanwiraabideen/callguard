// "Try to scam me": sends the microphone to the backend down the same path as a
// simulated call. The person playing the scammer is the caller channel.

import { toInt16, type CallController, type EndReason } from "./callPlayer";
import { MIC_SAMPLE_RATE } from "./config";

export async function startMicCall(
  socket: WebSocket,
  isSpeakingAsUser: () => boolean,
  onPlayed: (seconds: number) => void,
  onEnded: (reason: EndReason) => void,
  onLevel: (level: number) => void,
): Promise<CallController> {
  const context = new AudioContext({ sampleRate: MIC_SAMPLE_RATE });
  await context.audioWorklet.addModule("/micProcessor.js");
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });

  socket.send(JSON.stringify({ type: "call_start", call_id: "live" }));

  const source = context.createMediaStreamSource(stream);
  // With no outputs, the browser keeps it running without playing the mic back.
  const processor = new AudioWorkletNode(context, "mic-processor", {
    numberOfOutputs: 0,
  });
  source.connect(processor);

  let framesSent = 0;
  let ended = false;

  function finish(reason: EndReason) {
    if (ended) return;
    ended = true;
    processor.port.onmessage = null;
    source.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    context.close();
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "call_end", reason }));
    }
    onEnded(reason);
  }

  processor.port.onmessage = (event: MessageEvent<Float32Array>) => {
    if (socket.readyState !== WebSocket.OPEN) {
      finish("connection_lost");
      return;
    }

    // The other channel stays silent, so each voice stays with one speaker.
    const samples = event.data;
    // Loudest sample in this chunk, from 0 (silent) to 1, for the level meter.
    onLevel(samples.reduce((loudest, sample) => Math.max(loudest, Math.abs(sample)), 0));
    const speakerOffset = isSpeakingAsUser() ? 1 : 0;
    const pcm = new Int16Array(samples.length * 2);
    samples.forEach((sample, index) => {
      pcm[index * 2 + speakerOffset] = toInt16(sample);
    });

    socket.send(pcm.buffer);
    framesSent += samples.length;
    onPlayed(framesSent / MIC_SAMPLE_RATE);
  };

  // A live user is a real person, so there's nothing to lower or mute.
  return { stop: finish, setCallerLevel: () => {}, muteUser: () => {} };
}
