# Games: the standard a game is built to

What a Claude Code session reads when the request is a game (the widget's "Jeu" instruction points here). It is a standard of quality, not a template: the genre, 2D or 3D, the number of players, real time or turn by turn, the platforms come from the request, and what is missing is asked before building. It is written in French because the widget speaks French.

## 1. Choose by need, say why

| The request | Foundation |
|---|---|
| Solo, two players, turn by turn, a party game, a mini-game | One HTML file (Store mode) or a site (Pages mode), checked with a headless browser. |
| Results, scores, tokens or rewards that anyone must be able to verify, without a server | An Aiwa contract: the rules are replayed by each holder from signed events. Aiwa is the authority. |
| Real-time multiplayer (arena, co-op, race), 2D or 3D, from 2 to 16 players | **Godot 4 + Nakama** below: authoritative server, rooms, matchmaking, presence. Aiwa can still carry identity and verifiable rewards. |

Never announce a capacity (8, 16 players) that was not measured.

## 2. Godot + Nakama foundation

One common base, several game modules, network rules suited to each genre. The platform shares services and conventions; each game keeps its scenes, rules, physics and interface. No universal gameplay engine.

**Stack.** Godot 4.x (a pinned stable version), typed GDScript; Nakama (authentication, profiles, matchmaking, rooms, presence, friends, notifications, leaderboards, storage, server logic); Docker Compose for a reproducible backend; Git and continuous integration. Versions of the engine, the SDK, the containers and the dependencies are pinned in the repository. No paid proprietary service for the base. No administration secret in a mobile application. The server logic uses a language the Nakama runtime officially supports, chosen and pinned after a technical prototype. Read the official documentation of the pinned versions: never invent an SDK method or a deployment command.

**Accounts.** Guest login, session creation and renewal, nickname and avatar, profile load and update, explicit authentication errors, session recovery after the app is closed, preparation for a durable account later, clean logout. Session identifiers are stored appropriately on the device; no server secret in the app.

**Lobby.** Public or private game, an unpredictable invitation code with validation and expiry, participants and their connection state, minimum and maximum players, leaving, cancelling, launch requests, joining after the start only when the mode allows it, the lobby leader and its transfer, an error for a full, closed or missing game. No hard-coded game size or mode.

**Matchmaking.** Game and mode, number of players, region, public or private, skill level when there is a ranking, maximum wait, abandon and replacement policy. A search that expires ends in an explicit state, with no ghost session or lobby.

**Life of a match.** An explicit state machine: lobby created, waiting for players, preparation and synchronisation, match running, results validated, closing and cleanup. In competitive modes the server validates transitions: a client cannot force "results validated". Abandons, disconnections, timeouts and server errors have documented transitions. A finished match never pays the same reward twice.

**Layers.** Presentation (menus, HUD, accessibility), gameplay (rules, entities, collisions), game services (session, matchmaking, lobby, results, profile), network transport (connection, messages, reconnection, latency), backend (authoritative validation, storage, ranking, identity). Scenes never call the Nakama API everywhere: they go through services with stable interfaces.

**Game manifest.** Unique identifier and version, rendering (2D or 3D), mode, minimum and maximum players, network type, victory rule, reconnection rules, session parameters, server-side validation required. Static, versioned modules first; no dynamic plugin system in the first version.

**Network contracts.** Documented, versioned message schemas (`lobby.join`, `lobby.leave`, `match.ready`, `game.input`, `game.state`, `match.finished`, `player.reconnected`, `result.confirmed` are proposed conventions, not existing Nakama names). Messages are validated for size, type, frequency and content. Schema changes stay compatible with the deployed client and server.

**2D and 3D.** The services are shared, the scenes and the simulation are not: each module has its own scenes, cameras, controls, collisions and gameplay tests.

## 3. Tests

- **Unit:** match state transitions, lobby parameters, score computation, victory conditions, invalid commands, idempotent rewards, message serialisation, turn and timer rules.
- **Integration (a real backend):** guest authentication, lobby creation and closing, matchmaking between accounts, joining a match, message exchange, server validation, result persistence, session renewal, reconnection after a cut, refusal of an unauthorised command.
- **Multi-client and load:** 2 players (a whole match on two distinct clients); 4 (the same official transitions); 8 (the planned load scenario without critical errors); 16 (a capacity test with latency, CPU, memory and traffic measured); network cut (a reconnecting state and the game's policy); abandon; double command (no result or reward applied twice); forged command (the server rejects it); server restart (the documented recovery). Numeric thresholds are set after the first measurements on representative devices.
- **Continuous integration:** format, unit tests, the test backend, integration tests, configuration and dependency checks, test artefacts, and a clear report of what passed, failed or did not run. Signed production builds and real deployments are separate steps with explicit validation.

## 4. Order of work

1. Reproducible base: repository, Godot project, Docker, documentation, first tests; Nakama starts and the SDK is installed.
2. Identity and network: guest session, renewal, network errors, common services; a client connected to the backend.
3. Lobby and matchmaking; four clients in one lobby.
4. First playable prototype: a small 2D arena, touch movement, collisions, a simple goal, a result; playable on several devices.
5. Authority and security: commands, victory conditions and rewards validated by the server; forged actions tested.
6. Other genres (party, co-op, strategy, platform) on the common services.
7. Robustness and capacity: reconnection, abandons, mobile devices, load at 4, 8 then 16; a report with the measured limits.
8. Mobile pre-production: Android and iOS exports, staging, backups, supervision, deployment documentation. Real devices only count as tested when tried.

Never start a phase when the previous one fails a blocking criterion.

## 5. What a delivery contains

The openable Godot project, the Nakama server modules and their source, the Docker files and development configuration, a really playable multiplayer example, examples for several genres, unit and integration tests, multi-client tests and load tools, the architecture and network-contract documentation, the setup and troubleshooting procedure, the Android and iOS export procedure, an inventory of the dependencies and their licences, a report of the known limits and the measured performance.

## 6. How the session works

Inspect the repository and the environment before changing anything. Propose a short technical plan before each important phase. Change the files for real, run the commands and the tests, fix the errors before going on. Do not replace a missing feature with an unsignalled simulation. Write down the important architecture decisions. Say what is finished, what is tested and what remains. Never claim that a build, a test or a deployment succeeded without the proof of its execution. The first goal is not a huge tree of files but to show that Godot, the Nakama SDK, the server and two real clients work together.

Official references: Godot documentation (docs.godotengine.org), Nakama documentation (heroiclabs.com/docs/nakama), the Nakama guide for Godot 4, authoritative multiplayer, installation with Docker Compose, Android and iOS export in Godot.

## 7. What the widget cannot do for you

The Nakama server has to be hosted somewhere and a hosted server costs money; iOS needs an Apple developer account and a macOS machine; a Godot web export with threads needs cross-origin isolation headers that GitHub Pages cannot send (use the single-thread export). A game that needs them says so before building.
