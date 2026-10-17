"use client";
import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import { MediaManager } from "@/lib/webrtc/mediaManager";
import { VideoPlayer } from "./VideoPlayer";

function AudioTrack({ track }: { track: Track }) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => { const audio = ref.current; if (!audio) return; track.attach(audio); return () => { track.detach(audio); }; }, [track]);
  return <audio ref={ref} autoPlay controls aria-label="Instructor audio" className="w-full" />;
}
export function LectureMedia({ sessionId, identity, instructor = false }: { sessionId: string; identity: string; instructor?: boolean }) {
  const generation = useRef(0);
  const manager = useRef<MediaManager | null>(null);
  const room = useRef<Room | null>(null);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [camera, setCamera] = useState(false);
  const [microphone, setMicrophone] = useState(false);
  const [screen, setScreen] = useState(false);
  const [tracks, setTracks] = useState<Track[]>([]);
  useEffect(() => () => { generation.current++; manager.current?.disconnect(); }, []);
  const refresh = (r: Room) => {
    const participants = instructor ? [r.localParticipant] : [...r.remoteParticipants.values()];
    setTracks(participants.flatMap(p => [...p.trackPublications.values()].flatMap(pub => pub.track ? [pub.track] : [])));
    setCamera(r.localParticipant.isCameraEnabled); setMicrophone(r.localParticipant.isMicrophoneEnabled); setScreen(r.localParticipant.isScreenShareEnabled);
  };
  const connect = async () => {
    const attempt = ++generation.current;
    setBusy(true); setError("");
    const media = new MediaManager(); manager.current?.disconnect(); manager.current = media;
    try {
      const r = await media.connect(sessionId, identity, instructor);
      if (attempt !== generation.current) { media.disconnect(); return; }
      room.current = r;
      for (const event of [RoomEvent.TrackSubscribed, RoomEvent.TrackUnsubscribed, RoomEvent.LocalTrackPublished, RoomEvent.LocalTrackUnpublished]) r.on(event, () => refresh(r));
      r.on(RoomEvent.Disconnected, () => { setConnected(false); setTracks([]); });
      refresh(r); setConnected(true);
      await r.startAudio();
    } catch (err) { media.disconnect(); setError(err instanceof Error ? err.message : "Could not connect to lecture media. Check that the media server is running."); }
    finally { setBusy(false); }
  };
  const toggle = async (kind: "camera" | "microphone" | "screen") => {
    if (!room.current) return; setBusy(true); setError("");
    try {
      const p = room.current.localParticipant;
      if (kind === "camera") await p.setCameraEnabled(!p.isCameraEnabled);
      if (kind === "microphone") await p.setMicrophoneEnabled(!p.isMicrophoneEnabled);
      if (kind === "screen") await p.setScreenShareEnabled(!p.isScreenShareEnabled);
      refresh(room.current);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not access this device. Check browser permissions and retry."); }
    finally { setBusy(false); }
  };
  const video = tracks.find(t => t.source === Track.Source.ScreenShare) || tracks.find(t => t.kind === Track.Kind.Video);
  return <section aria-label="Live lecture" className="space-y-3 rounded-xl bg-white p-4 shadow">
    <div className="flex flex-wrap items-center gap-3">
      <h2 className="font-semibold flex-1">{instructor ? "Lecture broadcast" : "Live lecture"}</h2>
      {!connected && <button disabled={busy} onClick={connect} className="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50">{busy ? "Connecting…" : instructor ? "Connect broadcast" : "Join lecture audio and video"}</button>}
      {connected && instructor && <>
        <button disabled={busy} aria-pressed={microphone} onClick={() => toggle("microphone")} className="rounded border px-3 py-2">{microphone ? "Mute" : "Enable microphone"}</button>
        <button disabled={busy} aria-pressed={camera} onClick={() => toggle("camera")} className="rounded border px-3 py-2">{camera ? "Stop video" : "Enable camera"}</button>
        <button disabled={busy} aria-pressed={screen} onClick={() => toggle("screen")} className="rounded border px-3 py-2">{screen ? "Stop sharing" : "Share slides / screen"}</button>
      </>}
    </div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <VideoPlayer track={video} muted={instructor} />
    {!instructor && tracks.filter(t => t.kind === Track.Kind.Audio).map((track, i) => <AudioTrack key={track.sid || i} track={track} />)}
    <p className="text-xs text-gray-600">{instructor ? "Your enabled microphone, camera and shared screen are broadcast to students." : "Your webcam stays on your device. Only the instructor broadcasts media."}</p>
  </section>;
}
