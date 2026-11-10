// Plays a simulated call and sends the same audio to the backend as it plays.
// Both follow the audio clock, so the backend hears each moment as it is played.

import { AGENT_HOLD_LINE_MS, AUDIO_SEND_INTERVAL_MS, BACKEND_URL } from "./config";
import { passcodeHeaders } from "./passcode";

export type CallInfo = {
  id: string;
  title: string;
  duration_seconds: number;
  sample_rate: number;
};

export type EndReason =
  | "finished"
  | "stopped"
  | "connection_lost"
  | "agent_ended"
  | "call_limit";

// What the rest of the page can do to a running call, simulated or live.
export type CallController = {
  stop: (reason: EndReason) => void;
  setCallerLevel: (level: number) => void;
};

// The browser decodes audio to numbers from -1 to 1. This converts them back to
// the original 16-bit whole numbers.
export function toInt16(sample: number): number {
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

export async function playCall(
  call: CallInfo,
  socket: WebSocket,
  onPlayed: (seconds: number) => void,
  onEnded: (reason: EndReason) => void,
  isAgentTakingOver: () => boolean,
): Promise<CallController> {
  // Using the call's own sample rate means the browser doesn't resample it.
  const context = new AudioContext({ sampleRate: call.sample_rate });
  const response = await fetch(`${BACKEND_URL}/calls/${call.id}/audio`, {
    headers: passcodeHeaders(),
  });
  const audio = await context.decodeAudioData(await response.arrayBuffer());

  // Each channel goes to both ears. The caller has its own volume so that it
  // can be lowered during a whisper.
  const source = context.createBufferSource();
  const splitter = context.createChannelSplitter(2);
  const callerGain = context.createGain();
  source.buffer = audio;
  source.connect(splitter);
  splitter.connect(callerGain, 0);
  callerGain.connect(context.destination);
  splitter.connect(context.destination, 1);

  socket.send(JSON.stringify({ type: "call_start", call_id: call.id }));

  const startTime = context.currentTime + 0.1;
  let framesSent = 0;
  let ended = false;
  let holdTimer: ReturnType<typeof setTimeout>;

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
    clearTimeout(holdTimer);
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

  source.onended = () => {
    // A real line stays open when someone stops talking, so if the agent is
    // part way through a takeover, give it time to finish and hang up.
    if (isAgentTakingOver()) {
      sendUpTo(audio.length);
      holdTimer = setTimeout(() => finish("finished"), AGENT_HOLD_LINE_MS);
    } else {
      finish("finished");
    }
  };
  source.start(startTime);

  return {
    stop: finish,
    setCallerLevel: (level) => {
      if (!ended) {
        callerGain.gain.setTargetAtTime(level, context.currentTime, 0.05);
      }
    },
  };
}
