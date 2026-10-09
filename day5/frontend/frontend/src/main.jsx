import React from "react";
import { createRoot } from "react-dom/client";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  BarVisualizer,
  useRoomContext,
  useChat,
} from "@livekit/components-react";
import { RoomEvent } from "livekit-client";
import "@livekit/components-styles";
import "./style.css";

const API_URL = "http://127.0.0.1:8000";

function VoicePanel({ onDisconnect }) {
  const { state, audioTrack } = useVoiceAssistant();
  const room = useRoomContext();
  const { chatMessages } = useChat();
  const [transcripts, setTranscripts] = React.useState([]);
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    if (!room) return;

    const handleTranscription = (transcriptions) => {
      if (!transcriptions || transcriptions.length === 0) return;
      setTranscripts((prev) => [
        ...prev,
        ...transcriptions.map((t) => ({
          id: t.id || Math.random().toString(36).substring(7),
          sender: t.participantIdentity === room.localParticipant?.identity ? "user" : "assistant",
          text: t.text,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        })),
      ]);
    };

    room.on(RoomEvent.TranscriptionReceived, handleTranscription);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscription);
    };
  }, [room]);

  React.useEffect(() => {
    if (chatMessages && chatMessages.length > 0) {
      const latest = chatMessages[chatMessages.length - 1];
      setTranscripts((prev) => [
        ...prev,
        {
          id: latest.id || Math.random().toString(),
          sender: latest.from?.identity === room?.localParticipant?.identity ? "user" : "assistant",
          text: latest.message,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        },
      ]);
    }
  }, [chatMessages, room]);

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  const stateLabels = {
    speaking: "CityCare is speaking...",
    listening: "Listening to you...",
    thinking: "Processing response...",
    idle: "Assistant ready",
    connecting: "Connecting to clinic...",
  };

  return (
    <section className="voice-card connected-card">
      <div className={`orb ${state}`}>
        {state === "speaking" ? "🔊" : state === "listening" ? "🎙️" : "🏥"}
      </div>
      <h2>{stateLabels[state] || "CityCare Voice Assistant"}</h2>
      <p className="status">Status: <strong>{state}</strong></p>

      <div className="visualizer">
        {audioTrack && <BarVisualizer state={state} trackRef={audioTrack} barCount={7} />}
      </div>

      <div className="transcript-box" ref={scrollRef}>
        <div className="transcript-header">Live Conversation Transcript</div>
        {transcripts.length === 0 ? (
          <p className="transcript-placeholder">
            Speak to the receptionist. Live transcripts will display here in real time...
          </p>
        ) : (
          transcripts.map((t, index) => (
            <div key={index} className={`transcript-row ${t.sender}`}>
              <span className="transcript-sender">
                {t.sender === "user" ? "You" : "CityCare"}:
              </span>
              <span className="transcript-text">{t.text}</span>
            </div>
          ))
        )}
      </div>

      <button className="end-button" onClick={onDisconnect}>
        End Call
      </button>
    </section>
  );
}

function App() {
  const [connection, setConnection] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [name, setName] = React.useState("Sai");

  async function startCall() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/token?name=${encodeURIComponent(name || "Guest")}`);
      if (!response.ok) throw new Error(`Token API failed (${response.status})`);
      const data = await response.json();
      setConnection(data);
    } catch (e) {
      setError(`${e.message}. Ensure backend is running on port 8000.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header>
        <div className="brand-icon">🏥</div>
        <div>
          <h1>CityCare Clinic</h1>
          <p>AI Voice Receptionist & Clinical Assistant</p>
        </div>
        <span className="online"><i /> Online & Ready</span>
      </header>

      <section className="hero">
        <span className="eyebrow">ENTERPRISE VOICE AI CLINIC</span>
        <h2>Compassionate Care,<br />Instant Voice Assistance.</h2>
        <p>Book check-ups, cancel appointments, check opening hours, view billing details, and request prescription refills instantly.</p>
      </section>

      {!connection ? (
        <section className="voice-card">
          <div className="orb">🎙️</div>
          <h2>Talk to CityCare</h2>
          <p>Click below to begin your voice consultation.</p>

          <label htmlFor="caller-name">Your Full Name</label>
          <input
            id="caller-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
            placeholder="e.g. Sai"
          />

          <button className="start-button" disabled={loading} onClick={startCall}>
            {loading ? "Connecting to LiveKit..." : "Start Voice Call"}
          </button>
          {error && <p className="error">{error}</p>}
          <p className="privacy">🔒 End-to-end encrypted voice session via LiveKit Cloud.</p>
        </section>
      ) : (
        <LiveKitRoom
          serverUrl={connection.serverUrl}
          token={connection.participantToken}
          connect={true}
          audio={true}
          video={false}
          onDisconnected={() => setConnection(null)}
          onError={(e) => setError(e.message)}
        >
          <VoicePanel onDisconnect={() => setConnection(null)} />
          <RoomAudioRenderer />
          {error && <p className="error">{error}</p>}
        </LiveKitRoom>
      )}

      <footer>
        <span>CityCare Clinic &copy; 2026</span>
        <span>Mon–Fri: 8:00 AM – 6:00 PM | Sat: 9:00 AM – 1:00 PM | 12 Park Road</span>
      </footer>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
