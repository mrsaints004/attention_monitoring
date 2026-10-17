import { authHeaders } from "../credentials";
import { Room, RoomEvent, Track, RemoteParticipant } from "livekit-client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class MediaManager {
  private room: Room | null = null;
  private onTrackSubscribed: ((track: Track, participant: RemoteParticipant) => void) | null = null;

  async connect(sessionId: string, identity: string, isInstructor: boolean) {
    const res = await fetch(
      `${API_BASE}/api/sessions/${sessionId}/rtc-token?identity=${encodeURIComponent(identity)}&instructor=${isInstructor}`,
      { method: "POST", headers: authHeaders(sessionId, isInstructor) }
    );
    if (!res.ok) throw new Error("Lecture access denied. Please rejoin the session.");
    const { token } = await res.json();

    this.room = new Room();

    this.room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      this.onTrackSubscribed?.(track, participant);
    });

    const livekitUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL || "ws://localhost:7880";
    await this.room.connect(livekitUrl, token);

    return this.room;
  }

  async publishCamera() {
    if (!this.room) return;
    await this.room.localParticipant.setCameraEnabled(true);
  }

  async publishScreen() {
    if (!this.room) return;
    await this.room.localParticipant.setScreenShareEnabled(true);
  }

  setOnTrackSubscribed(cb: (track: Track, participant: RemoteParticipant) => void) {
    this.onTrackSubscribed = cb;
  }

  disconnect() {
    this.room?.disconnect();
    this.room = null;
  }
}
