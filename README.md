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

## Facial-affect model and training

The installed `/models/fer` release is a face-pretrained MobileNet fine-tuned on all 5,358 labelled DAiSEE training clips, with engagement, boredom and confusion heads. A single seed-42 run completed; validation selected `fine_tune-0014`. Python/JavaScript conversion parity passed at absolute tolerance 0.0001. The lecture page uses these outputs directly; it does not run the old pilot alongside the full model.

`/dataset-review` presents the measured full-run results: 1,399/1,429 scorable validation clips and 1,780/1,784 scorable held-out test clips. Test accuracy / macro-F1: engagement 44.3% / 0.288; boredom 42.0% / 0.352; confusion 48.9% / 0.309. Engagement accuracy remains below the majority baseline, so the classifier should not be represented as highly accurate. These results do not establish fused-system improvement or live-device performance. Earlier pilot artifacts remain archived separately. Raw videos and face crops stay outside Git.

To reproduce the sample experiment with an existing FFmpeg installation:

```bash
python3 -m training.sample_inventory --sample daisee_sample --output training/prepared/sample-new --ffmpeg /path/to/ffmpeg
node training/sample_pilot.cjs training/prepared/sample-new training/runs/sample-new
node training/verify_sample_pilot.cjs training/prepared/sample-new training/runs/sample-new
```

Use new output directories for new runs. These commands preserve the supplied partitions; they do not replace the full-corpus workflow below. The pilot has no boredom/confusion heads. Its verified deployment files are in `frontend/public/models/daisee-pilot`, separately from the three-head `fer` model. The student lecture page runs the pilot locally at up to 2 FPS when monitoring has a reliable camera frame, checks model/weight SHA-256 hashes before loading, and shows its engagement predictions separately from the Attention Index. Pause, unreliable images and inactive tabs withhold pilot output. Live resizing is bilinear, while the original FFmpeg frame scaling differs; its four-clip test accuracy is not a live accuracy guarantee. Regenerate the deployment assets using `node training/publish_sample_pilot.cjs`, which first replays the measured predictions.


Check the available training evidence before preparing research results:

```bash
python3 -m training.readiness --output training/artifacts/readiness.json
# After obtaining and training on the official dataset:
python3 -m training.readiness --dataset /path/to/DAiSEE --run training/runs/run-001
```

The audit exits with status 2 when evidence is incomplete. It checks dataset partitions, checkpoint provenance, validation/test reports and browser model files. Passing these checks establishes the affect-model artifacts only; it does not establish the fused-model comparison, volunteer trials or measured live performance required by the research methodology. Evaluation reports include four-class per-class metrics and binary engagement metrics (labels 0/1 versus 2/3), counting unavailable clips separately and as errors in all-clip accuracy.

The application supports a face-pretrained MobileNet adapted to DAiSEE. The starting checkpoint is EmotiEffLib's `mobilenet_7.h5`; its existing emotion classifier is replaced by three four-level outputs: **engagement**, **boredom**, and **confusion**. Its native **224×224 RGB** input and source mean subtraction are retained. A general emotion classifier is never treated as a trained engagement classifier.

The offline training workflow is separate from website hosting. A finished checkpoint is not included: DAiSEE must be obtained through its [official download page](https://people.iith.ac.in/vineethnb/resources/daisee/index.html), and the training steps must actually run before the fourth cue becomes available. Keep dataset images and intermediate checkpoints out of the public repository.

Generated notebooks are kept out of Git. Run `python3 scripts/build_full_training_notebook.py` from the repository root to create the current full-training and preparation notebooks. For full training, upload `training/full_daisee_colab.ipynb` at [Google Colab](https://colab.research.google.com/), select a GPU runtime, and run its cells in order. The notebook embeds its training source, so no repository push is needed. It first checks GPU access and exercises checkpoint loading, weighted updates, optimizer restoration and browser conversion before transferring data. The approved Drive archive ID is already configured; all videos referenced by the supplied official label CSVs are downloaded directly into Colab, with size/CRC checks and resumable retrieval.

The full protocol uses three seeds (42, 52, 62), up to 30 head-training and 20 fine-tuning epochs per seed, and validation macro-F1 for checkpoint/run selection. Per-epoch model/optimizer checkpoints and reports are saved to Drive. The selected model receives held-out evaluation with participant-bootstrap intervals, followed by browser export and Python/JavaScript prediction checks. Runtime errors remain visible and are saved to logs. Training has not been completed merely by generating this notebook.

To avoid spending GPU allocation on retrieval/preparation, first run `training/prepare_daisee_colab.ipynb` in a CPU runtime. It saves a hash-verified `prepared-2fps.zip` to Drive. Then run the GPU notebook with the same `daisee-full-2fps-v3` experiment name; it restores those crops and skips video retrieval. Keep settings unchanged when resuming. Local `/content` video/crop files are ephemeral, while the prepared ZIP and checkpoints persist in Drive. Allow enough Drive quota for that ZIP plus checkpoints. Raw videos, crops and multiple model checkpoints require substantial cloud storage, and three runs may span multiple GPU sessions. Download the completed `daisee-full-trained-release.zip` and copy its `fer/` directory into `frontend/public/models/fer/`. Use the generated full-training notebook for this protocol; older local notebooks are not part of the repository.

For a local Python 3.10/3.11 environment, run these commands from the repository root:

```bash
python3.11 -m venv training/.venv
training/.venv/bin/python -m pip install -r training/requirements-export.txt
npm ci --prefix frontend
training/.venv/bin/python -m training.fetch_pretrained
training/.venv/bin/python -m training.prepare --dataset /path/to/DAiSEE --output training/prepared
training/.venv/bin/python -m training.train --prepared training/prepared --output training/runs/run-001
training/.venv/bin/python -m training.evaluate --prepared training/prepared --run training/runs/run-001 --split validation
training/.venv/bin/python -m training.export --run training/runs/run-001
```

The dataset is expected to contain `Labels/TrainLabels.csv`, `ValidationLabels.csv`, `TestLabels.csv`, and the `DataSet/Train`, `Validation`, `Test` video directories. Preparation processes ordered video frames at up to 2 FPS, uses one-face/lighting checks and the same face-crop margin as the browser, and records undecodable clips or clips with no usable frames for coverage reporting. Prepared crops can require substantially more disk space than the downloaded archive.

The workflow preserves official partitions and rejects subject/clip leakage. Training starts with a frozen face backbone, then fine-tunes its later layers while keeping batch-normalisation layers frozen. Clip-balanced, class-weighted losses are used. The checkpoint is selected by validation **clip-level engagement macro-F1**, not frame-level accuracy. Reports include all-clip coverage and account for clips without usable faces.

Export requires a completed training record and matching validation report. It compares Python and TensorFlow.js predictions on three RGB probes and refuses publication if conversion does not match. Dependency installation, full training and real-checkpoint conversion must be verified in the training environment; lightweight project tests do not establish those results.

The generated deployment directory contains `model.json`, binary weight shards, `metadata.json`, and source/licence records. Browser loading checks the native input shape, class order, three output heads, completion metadata and warm-up predictions. When any check fails or model assets are absent, the application uses explicitly labelled **three-cue geometric mode**. In four-cue mode, affect scores are averaged over two seconds; boredom/confusion estimates appear in student detail and exports.

To perform the held-out test after freezing model selection:

```bash
training/.venv/bin/python -m training.evaluate --prepared training/prepared --run training/runs/run-001 --split test --confirm-final-test
```

This evaluates the affect classifier. Fitting the fused system's weights/cut-points, comparing the fused and affect-only systems, and volunteer trials remain separate research work. No accuracy target or hypothesis result is claimed without those measurements. Review upstream checkpoint and dataset redistribution terms before publishing trained weights; preserve their required notices.

Backbone and preprocessing references: [EmotiEffLib](https://github.com/sb-ai-lab/EmotiEffLib) and its [AffectNet training notebook](https://github.com/sb-ai-lab/EmotiEffLib/blob/main/training_and_examples/affectnet/train_emotions.ipynb).

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

Backend tests use an isolated in-memory database, and migration tests use temporary database files. Frontend tests exercise scoring, geometry, class averaging, telemetry sampling/buffering and MobileNet input contracts. Offline data-contract tests run with `python3 -m unittest discover -s training/tests`. Automated tests do not replace live webcam and lecture-stream testing.

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

For Vercel, select `frontend` as the project root and configure `NEXT_PUBLIC_API_URL` with the backend HTTPS URL, `NEXT_PUBLIC_WS_URL` with its WSS URL, and `NEXT_PUBLIC_LIVEKIT_URL` with the production LiveKit WSS URL before building. Host the stateful FastAPI WebSocket service separately on a persistent server; Vercel Functions do not act as WebSocket servers ([Vercel guidance](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections)).

On that backend host, install `backend/requirements.txt`, activate the Python environment, set the following variables, and run `sh start.sh` from `backend/`:

```text
APP_ENV=production
AUTH_SECRET=<a stable private random value, at least 32 characters>
CORS_ORIGINS=["https://your-frontend-domain"]
DATABASE_URL=sqlite+aiosqlite:////var/data/attention_monitor.db
LIVEKIT_URL=wss://your-production-livekit-host
LIVEKIT_API_KEY=<your production API key>
LIVEKIT_API_SECRET=<your production API secret, at least 32 characters>
```

Mount persistent storage at the SQLite location and ensure the directory exists and is writable. `sh start.sh` applies migrations before starting exactly one API worker and limits WebSocket message size to 64 KiB. Production settings reject development media credentials, an unset/generated signing key, insecure origins, insecure LiveKit URLs and relative SQLite paths. Local examples stay in development mode.

The full three-head DAiSEE classifier is trained, held-out evaluated, parity checked and installed in `frontend/public/models/fer`. The Attention Index incorporates the engagement estimate when reliable affect inference is available, with geometric fallback otherwise. Live webcam/LiveKit verification and production deployment still require their respective devices and service configuration.


Use HTTPS/WSS, production LiveKit credentials and appropriate media networking. Configure a stable private signing secret, explicit allowed origins, database backups and a participant-data retention policy. Back up existing databases before applying migrations.

Start with a single API worker: connection and alert state are stored in process memory. Multiple workers require shared state. Session capabilities are a lightweight access mechanism, not an institutional account system.

Environment secrets, research documents, local databases, dependencies, backups and generated output are excluded from version control. Example environment files are included for configuration.


## Deployment and verification tools

`render.yaml` and `backend/Dockerfile` define a persistent, single-worker backend template. The template selects a paid Render service; creating it requires your hosting account and production LiveKit settings. No service is provisioned by adding these files. Follow `deploy/START_HERE.txt` for the backend/Vercel configuration and the two-device acceptance trial.

The database readiness endpoint is `/api/ready`; it returns 503 if the database or required migrated columns are unavailable. The independent `/api/health` endpoint remains a process-liveness check. From a configured backend environment, create a consistent private backup with `python -m app.backup --output /var/data/backups`; retain an off-service copy as well.

After a production build, `npm run test:e2e` from `frontend` runs browser integration tests against isolated local services. Set `ATTENTION_BACKEND_PYTHON` if the backend interpreter is not detected automatically. CI runs backend, frontend, training-contract and browser checks. Live camera/MediaPipe calibration and LiveKit delivery still require the acceptance trial on actual devices.

To install a future completed full-model bundle from the repository root:

```bash
python3 -m training.install_release --archive /path/to/daisee-full-trained-release.zip
```

Installation checks archive paths, content hashes, matching dataset/preparation inventories, checkpoint/evaluation evidence, model metadata and weight files. It refuses to overwrite an existing release. The 12-clip pilot cannot satisfy the full-model installer.

The frontend pins Next.js and its lint configuration to 16.4.6. Scoped overrides update Zod and the TypeScript parser’s minimatch dependency to patched versions; regression tests, lint and build must pass when changing these overrides. The most recent successful installation audit reported zero frontend dependency vulnerabilities. This does not audit the Python environment.


## Full dataset available locally

The supplied `DAiSEE.zip` has been extracted to `datasets/DAiSEE`: 5,358 training,
1,429 validation and 1,784 test clips across 109 subjects. One source ZIP CRC anomaly
is fingerprinted and explicitly recorded in `source_crc_exceptions.json`; its bytes
match an independent download from the original archive. The local runner decodes
and records that clip separately before preparing data.

On this Mac, start the full protocol with `./TRAIN_DAiSEE.command` from the project
root (or double-click that file). It installs the real runtime, checks GPU access,
prepares all clips at 2 FPS, trains three seeds, freezes validation selection,
evaluates the held-out checkpoint, verifies export parity, installs the browser
model and rebuilds the frontend. CPU-only training requires explicit `--allow-cpu`.
See `FULL DAISEE TRAINING/LOCAL_TRAINING.txt`. This command and the extracted dataset
are not evidence that training has already completed. Current execution status is
recorded in `training/artifacts/local_full_run_status.json`.
