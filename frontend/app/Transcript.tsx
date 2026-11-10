import { useEffect, useRef } from "react";

export type Speaker = "caller" | "user" | "agent" | "whisper";

export type TranscriptSegment = {
  speaker: Speaker;
  text: string;
  start: number;
  end: number;
  is_final: boolean;
};

const SPEAKER_LABELS: Record<Speaker, string> = {
  caller: "Caller",
  user: "You",
  agent: "Agent, to the caller",
  whisper: "Whisper, only you hear",
};

function Line({ segment }: { segment: TranscriptSegment }) {
  const isAgent = segment.speaker === "agent" || segment.speaker === "whisper";
  return (
    <p
      className="transcript-line"
      style={{
        margin: "4px 0",
        color: segment.is_final ? "inherit" : "gray",
        fontStyle: isAgent ? "italic" : "normal",
      }}
    >
      <small>{segment.start.toFixed(1)}s</small>{" "}
      <strong>{SPEAKER_LABELS[segment.speaker]}:</strong> {segment.text}
    </p>
  );
}

export function Transcript({
  finals,
  interim,
}: {
  finals: TranscriptSegment[];
  interim: Partial<Record<Speaker, TranscriptSegment>>;
}) {
  const boxRef = useRef<HTMLDivElement>(null);

  // Keep the newest words in view.
  useEffect(() => {
    if (boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight;
    }
  }, [finals, interim]);

  return (
    <div
      id="transcript"
      ref={boxRef}
      style={{ height: 240, overflowY: "auto", border: "1px solid gray", padding: 8 }}
    >
      {finals.map((segment, index) => (
        <Line key={index} segment={segment} />
      ))}
      {interim.caller && <Line segment={interim.caller} />}
      {interim.user && <Line segment={interim.user} />}
    </div>
  );
}
