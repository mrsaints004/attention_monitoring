# Attention Monitoring

A web-based platform for delivering online lectures and monitoring visual cues associated with student attention. Students process their webcam feed locally, while instructors receive numerical estimates, class summaries and alerts through a live dashboard.

The project is an experimental teaching aid. Its scores are estimates and should not be used for grading, attendance decisions or disciplinary action.

## Features

- Instructor sessions with shareable join codes.
- Consent, webcam setup and personal calibration before monitoring.
- Local eye-state, head-pose, gaze and yawn analysis.
- Attentiveness Index from 0 to 100, with smoothing and sustained-eye-closure handling.
- Instructor audio, video and screen sharing through LiveKit.
- Individual student cards, class averages and sustained-distraction alerts.
- Separate states for paused monitoring, inactive tabs, missing faces and unreliable images.
- Session history, class trends and CSV export.
- Session-scoped access credentials and student consent withdrawal with stored-data deletion.
- Reconnection and bounded buffering for temporary monitoring-network interruptions.

## Technology

| Layer | Tools |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Browser analysis | MediaPipe, TensorFlow.js |
| Charts | Recharts |
| Backend | FastAPI, WebSockets, SQLAlchemy |
| Database | SQLite with aiosqlite |
| Migrations | Alembic |
| Lecture media | LiveKit / WebRTC |
| Tests | pytest, Node.js test runner |

## Requirements

- Node.js 20.9 or newer; Node.js 24 is recommended for development and tests.
- Python 3.9 or newer.
- Docker with Docker Compose for the local lecture media server.
- A webcam and a modern browser with WebRTC support.
- Internet access for the initial browser-analysis runtime and model downloads.

Camera access requires `localhost` or HTTPS. The commands below use macOS/Linux paths.

## Installation

### 1. Clone and configure

```bash
git clone https://github.com/mrsaints004/attention_monitoring.git
cd attention_monitoring
python3 scripts/setup.py
```

The setup script creates `backend/.env` and `frontend/.env.local` from their example files without overwriting existing configuration. It also generates a private session-signing secret for a new backend configuration.

### 2. Start the backend

```bash
cd backend
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/alembic upgrade head
./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run backend commands from the `backend` directory so its environment file and database path resolve correctly.

- API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

### 3. Start the lecture media server

In a separate terminal, from the repository root:

```bash
docker compose -f sfu/docker-compose.yml up -d
```

The local development service uses `devkey` / `secret`, matching the backend defaults. These credentials are for local development only.

To stop it:

```bash
docker compose -f sfu/docker-compose.yml down
```

### 4. Start the frontend

In another terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`.

## Using the application

### Instructor

1. Select **Start a Session (Instructor)** and enter the session details.
2. Share the join code with students.
3. Select **Connect broadcast** in the console.
4. Enable the microphone or camera, or select **Share slides / screen**.
5. Review student states, class averages and alerts during the lecture.
6. End the session and open its history to review trends or export CSV data.

Instructor access is saved in the browser that creates the session. Keep that browser's local storage; opening the console URL in another browser does not grant instructor access.

### Student

1. Select **Join a Session (Student)** and enter the join code.
2. Read the monitoring explanation and give consent.
3. Choose a display alias, allow camera access and complete calibration.
4. Select **Join lecture audio and video** in the lecture room.
5. Pause monitoring or leave whenever needed. **Withdraw consent** deletes the stored alias and monitoring readings for that session; previously downloaded exports cannot be recalled.

For a local walkthrough, use separate browser profiles for instructor and student.

## How monitoring works

```text
Student webcam
    |
    v
Local landmarks and visual cues
    |
    v
Calibration, scoring and quality checks
    |
    v
Numerical readings over WebSocket
    |
    v
FastAPI --> Database --> Instructor dashboard
```

The instructor's lecture media travels separately through LiveKit. Student media tokens do not permit webcam or data-track publishing.

Analysis normally runs at 10 frames per second. Monitoring readings are sampled at approximately one update per second, with immediate quality-state changes. The client keeps a bounded, temporary offline buffer and attempts reconnection after a connection failure. Delivery is best-effort rather than guaranteed exactly-once delivery.

Unavailable readings use a `null` index rather than zero and are excluded from averages. Sustained face absence produces **Face Not Detected**, then **Away** after thirty seconds; calibration repeats when the face returns. Poor lighting, multiple faces and low processing rates can also withhold scoring.

## Facial-affect model and research status

A trained facial-affect model is **not included**. Without one, the application explicitly uses experimental **three-cue mode**: eye state, gaze/head pose and yawning. It renormalises the available weights and records `inference_mode=geometric`.

To enable the fourth cue, place a compatible TensorFlow.js Layers model at:

```text
frontend/public/models/fer/model.json
```

Include the model's referenced weight files in the same model directory. The required contract is:

- One grayscale input with shape `[1, 48, 48, 1]`, scaled to `[0, 1]`.
- One output containing four nonnegative engagement probabilities, ordered **Very Low**, **Low**, **High**, **Very High**.
- Affect score calculated as `(p1 + 2*p2 + 3*p3) / (3*sum(p))`.

A seven-expression emotion classifier is not interchangeable with this model. Model preprocessing, output ordering and accuracy must be validated before use.

Fusion weights and status thresholds are provisional. Classification accuracy, statistical improvement over a baseline, end-to-end latency and bandwidth targets have not been established through benchmark or volunteer evaluation. Boredom/confusion classifiers are not bundled.

## Configuration

Backend settings are read from `backend/.env`:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection URL |
| `AUTH_SECRET` | Stable private secret for instructor session capabilities |
| `CORS_ORIGINS` | JSON array of allowed frontend origins |
| `LIVEKIT_URL` | Media server address |
| `LIVEKIT_API_KEY` | Media server API key |
| `LIVEKIT_API_SECRET` | Media server signing secret |
| `ALERT_THRESHOLD` | Index below which a low-attention episode starts |
| `ALERT_DURATION_SECONDS` | Required episode duration before an alert |
| `ALERT_COOLDOWN_SECONDS` | Minimum interval between alerts per student |

Changing `AUTH_SECRET` invalidates existing instructor capabilities. Keep it private and stable across restarts.

Frontend settings are read from `frontend/.env.local`:

| Variable | Local value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` |
| `NEXT_PUBLIC_LIVEKIT_URL` | `ws://localhost:7880` |

Frontend public environment variables are embedded during builds. Rebuild after changing them for production.

## Tests and production build

Backend, from `backend`:

```bash
./venv/bin/python -m pytest -q
```

Frontend, from `frontend`:

```bash
npm test
npm run lint
npx tsc --noEmit
npm run build
npm run start
```

Backend tests use an isolated in-memory database, and migration tests use temporary database files. Frontend tests exercise scoring, geometry, class averaging and telemetry sampling/buffering. Automated tests do not replace live webcam and lecture-stream testing.

The frontend uses Webpack, allowing the framework's WebAssembly compiler fallback when native compiler bindings are unavailable. Builds use system fonts without downloading external fonts.

## Project structure

```text
backend/
  app/
    models/           Database models
    routers/          REST endpoints
    schemas/          Request and response validation
    services/         Sessions, alerts, dashboard and media tokens
    websockets/       Student and instructor connections
  alembic/            Database migrations
  tests/              Backend and migration tests
frontend/
  src/
    app/              Application pages
    components/       Shared interface components
    hooks/            Camera and connection lifecycle
    lib/              Scoring, transport and API helpers
  tests/              Frontend regression tests
scripts/              Local setup helper
sfu/                  Local LiveKit service configuration
```

## Troubleshooting

| Problem | Check |
| --- | --- |
| Camera access fails | Use localhost or HTTPS, grant permission and close other applications using the webcam. |
| Calibration does not finish | Keep one face visible, improve lighting and look at the screen with eyes open; restart calibration if needed. |
| Lecture media does not connect | Confirm LiveKit is running and its URL and credentials match the backend/frontend configuration. |
| Instructor access is denied | Use the browser profile that created the session and retain its local storage. |
| Three-cue mode appears | No compatible trained facial-affect model was loaded. Install and validate one to enable the fourth cue. |
| Database columns are missing | Back up the database, then run `./venv/bin/alembic upgrade head` from `backend`. |
| Frontend cannot reach the API | Start the backend and verify API/WebSocket URLs and allowed origins. |

## Deployment considerations

Use HTTPS/WSS, production LiveKit credentials and appropriate media networking. Configure a stable private signing secret, explicit allowed origins, database backups and a participant-data retention policy. Back up existing databases before applying migrations.

Start with a single API worker: connection and alert state are stored in process memory. Multiple workers require shared state. Session capabilities are a lightweight access mechanism, not an institutional account system.

Environment secrets, research documents, local databases, dependencies, backups and generated output are excluded from version control. Example environment files are included for configuration.
