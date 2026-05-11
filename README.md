# Jarvan

Asistente local multimodal estilo Jarvis, corriendo 100% en este equipo.
Servidor de IA: **Ollama local** en el mismo PC.
Prototipo para presentación a jefatura en laboratorio 3D.

> Objetivo: lo más cercano a Jarvis (Iron Man) que puede ejecutarse en un PC real,
> sin depender de servicios en la nube. Voz, visión, control del computador,
> planificación multi-paso, memoria persistente, audio design y UI flotante.

---

## 1. Qué puede hacer

### Conversa como Jarvis
- Saludo proactivo contextual al iniciar ("Buenos días. Núcleo Ollama en línea").
- Responde breve, formal-cercano, en español, te llama "señor".
- **Voz masculina grave** (piper si está, pyttsx3 buscando voz hombre-español como fallback).
- **Subtítulos karaoke**: cada palabra se ilumina en blanco al pronunciarse.
- **Filler talk**: si tarda más de 1.4s en responder, dice "Procesando, señor" o "Un momento" — nunca se queda mudo.
- **Audio design**: efectos UI sintéticos (boot, listen, confirm, error, alert, pop) generados sin assets externos.
- Modo conversación continua (hands-free) o por wake-word "Jarvan".
- Respuesta en streaming token a token visible en el HUD.

### Controla el computador
- Abre apps, URLs, carpetas. Escribe texto. Hotkeys.
- Click sobre **texto visible en pantalla** (OCR + VLM).
- Control de volumen, brillo, multimedia, bloqueo de pantalla.
- Lectura/escritura de archivos (sandbox limitado a `~`), PDFs.
- Ejecución de PowerShell con whitelist de comandos peligrosos.
- Búsqueda y reproducción **automática** de YouTube (autoplay del primer resultado).
- Navegación web headless con Playwright.

### Entiende el sistema
- Sabe sin preguntar: hora, día, ventana activa, apps abiertas, batería, CPU, RAM.
- Avisa proactivamente si la batería baja, la RAM se satura o detecta inactividad larga.
- Aprende preferencias del usuario automáticamente ("siempre prefiero Brave", "me llamo Claudio") y las recuerda entre sesiones.

### Arquitectura agentic real
- **Router de intención**: `chat` / `system_query` / `task` → no malgasta el modelo grande en saludos.
- **Planner Plan-and-Execute** con qwen2.5-coder:14b (optimizado para 16 GB VRAM).
- **Verifier VLM**: tras cada acción crítica, screenshot + qwen2.5-vl juzga si el resultado fue el esperado.
- **Replanning automático**: si un plan falla, replanifica con el error como contexto (hasta 2 reintentos).
- **Memoria a dos niveles**: ring buffer de conversación + SQLite + ChromaDB con embeddings.

---

## 2. Visual de la demo

- **Splash inicial** (2.6s, fade-in/out) + sonido `boot` ascendente.
- **Esfera flotante** sin marco, sin fondo, always-on-top, click-through cuando está idle.
- **Boot-up animation** tipo arc reactor (anillos cerrándose).
- **Estados con color**: BOOT blanco, IDLE azul, LISTENING verde, THINKING ámbar, SPEAKING violeta, ERROR rojo.
- **Reactividad real al audio**: el mic alimenta la animación al escuchar; el sistema de audio del SO la alimenta al hablar (vía pycaw + loopback). Si reproduces música, la esfera baila al ritmo.
- **Orbes luminosos** girando alrededor + halo radial + 4 anillos + 42 partículas + waveform circular.
- **HUD lateral** con transcripción del usuario y respuesta del agente con efecto **karaoke palabra a palabra** sincronizado con la voz.
- **Panel telemetría** top-left: GPU%, temperatura, VRAM usada, CPU%, RAM%, latencia del turno (nvidia-smi en tiempo real).
- **Panel contextual** top-right: reloj grande, fecha en español, ventana activa, batería con color dinámico, modelo LLM activo.
- **Tray icon** con menú: mostrar/ocultar esfera, HUD, telemetría, escuchar, salir.

---

## 3. Arquitectura

```
jarvan/
├── core/                       # Cerebro
│   ├── agent.py                # Orquestador (router → planner → executor)
│   ├── planner.py              # Plan-and-Execute con qwen2.5-coder, soporta replanning
│   ├── executor.py             # Ejecuta pasos, verifica, reintenta
│   ├── verifier.py             # VLM juzga post-acción (computer use real)
│   ├── router.py               # Clasifica intención antes del planner
│   ├── filler.py               # "Procesando, señor..." si tarda
│   ├── llm_client.py           # Cliente Ollama (chat, stream, JSON, visión, embed, warmup)
│   ├── health.py               # Health check de Ollama + modelos
│   ├── telemetry.py            # GPU/CPU/VRAM/latencia
│   ├── system_context.py       # Estado del SO inyectado cada turno
│   ├── proactive.py            # Avisos proactivos (batería, RAM, inactividad)
│   ├── preferences.py          # Aprendizaje automático de preferencias
│   ├── logger.py
│   └── memory/
│       ├── short_term.py       # Ring buffer
│       └── long_term.py        # SQLite + ChromaDB (embeddings)
├── perception/
│   ├── screen.py               # Captura mss con caché
│   ├── vision.py               # VLM qwen2.5-vl (entiende UI)
│   └── ocr.py                  # PaddleOCR + tesseract fallback + fuzzy
├── actuation/
│   ├── mouse.py                # Movimiento humanizado
│   ├── keyboard_ctrl.py
│   ├── windows_ctrl.py         # pywinauto / pygetwindow
│   ├── apps.py                 # Lanzador de apps
│   └── media.py                # Teclas multimedia + brillo
├── tools/                      # 24 herramientas
│   ├── registry.py             # Tool calling validado con pydantic
│   ├── builtin.py              # Computer use: open_app, click_text, observe, search_youtube...
│   ├── system_tools.py         # set_volume, screenshot, clipboard, time_now, run_shell
│   ├── file_tools.py           # read/write_file, list_dir, read_pdf, open_path
│   ├── media_tools.py          # media_control, set_brightness, lock_screen
│   └── web_tools.py            # fetch_url, web_search (Playwright)
├── io_layer/
│   ├── stt.py                  # faster-whisper GPU + VAD
│   ├── tts.py                  # piper / pyttsx3 con voz masculina-es + karaoke por palabra
│   ├── sfx.py                  # 8 sonidos UI sintéticos (boot, listen, confirm, error, alert...)
│   ├── audio_meter.py          # Mic + loopback sistema (pycaw)
│   └── wakeword.py             # openWakeWord o fallback Whisper-poll
├── ui/
│   ├── sphere.py               # Esfera flotante reactiva
│   ├── hud.py                  # HUD karaoke + telemetría + contextual
│   ├── splash.py               # Splash inicial
│   └── tray.py                 # System tray
├── config/
│   ├── settings.yaml           # Configuración tuneada para Quadro RTX 5000 (16 GB VRAM)
│   └── loader.py               # Carga validada con pydantic
├── data/                       # Memoria persistente, screenshots
├── logs/
├── tests/
├── main.py                     # GUI completa
├── cli.py                      # Modo texto (sin audio)
└── setup.ps1                   # Setup automatizado de Windows
```

### Pipeline por turno

```
trigger (Espacio | F8 continuo | wake-word "Jarvan" | doble-click esfera)
        ↓
   SFX listen_start  +  STT (Whisper GPU)
        ↓
   Aprender preferencias (background, modelo rápido)
        ↓
   SystemContext.gather()          ← hora, ventana, batería, etc (gratis)
        ↓
   Router.classify()
   ├─→ chat         → respuesta streaming (modelo rápido 8B)
   ├─→ system_query → respuesta con datos del SO (8B)
   └─→ task →
        Planner (14B) → plan con steps + expected
              ↓
        Executor + Verifier (VLM)
        ├─→ éxito → narrar resultado
        └─→ falla → replan con prior_failure (hasta 2 reintentos)
              ↑
   (Filler "Procesando, señor" si tarda >1.4s)
        ↓
   SFX confirm + TTS karaoke (cada palabra se ilumina en el HUD)
        ↓
   Loopback meter (pycaw) → esfera reactiva al audio real
        ↓
   Si modo continuo → volver al inicio
```

---

## 4. Equipo objetivo

Tuneado para el equipo del laboratorio:

| Componente | Modelo |
|---|---|
| Workstation | Dell Precision 5820 Tower |
| CPU | Intel Core i9-10900X (10c/20t) |
| RAM | 64 GB |
| GPU | NVIDIA Quadro RTX 5000 (~16 GB VRAM) |
| OS | Windows 11 Pro 64-bit |

Presupuesto VRAM estimado en uso normal: ~14 GB pico. Cabe cómodo en 16 GB sin swap a RAM.

---

## 5. Setup en Windows

### 5.1 Requisitos

- **Python 3.12** (recomendado por compatibilidad con paddlepaddle).
- **Ollama** instalado y corriendo: <https://ollama.com>
- **Drivers NVIDIA** recientes (Studio Driver, no Game Ready).
- **Tesseract OCR** (opcional, fallback): <https://github.com/UB-Mannheim/tesseract/wiki>

### 5.2 Modelos de Ollama (~20 GB en disco)

```powershell
ollama pull qwen2.5-coder:14b    # planner (~9 GB VRAM al cargar)
ollama pull qwen3:8b             # router rápido y chat (~5 GB)
ollama pull qwen2.5vl:7b         # visión (~6 GB)
ollama pull nomic-embed-text     # embeddings de memoria (~0.3 GB)
```

Verifica:
```powershell
ollama list
```

### 5.3 Instalación automatizada (recomendada)

```powershell
cd d:\jarvan
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

El script:
1. Verifica que `python` está en PATH.
2. Crea `.venv` si no existe.
3. Usa `python -m pip` (no depende de que `pip` esté en PATH).
4. Reintenta con `--trusted-host` y mirror alternativo si la red bloquea pypi.
5. Verifica Ollama.

### 5.4 Instalación manual

```powershell
cd d:\jarvan
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# IMPORTANTE: usar python -m pip por si pip no está en PATH
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

copy .env.example .env
```

### 5.5 Componentes opcionales

```powershell
# Navegación web real
playwright install chromium

# Wake-word con modelos precargados (si no, usa fallback Whisper-poll)
python -c "import openwakeword.utils as u; u.download_models()"
```

---

## 6. Cómo arrancar

### Demo completa (GUI)
```powershell
python main.py
```

Secuencia visual:
1. Splash con sonido `boot` ascendente (~2.6s).
2. Esfera con boot-up animation.
3. Aparecen 3 paneles flotantes: telemetría (izq), contextual (der), HUD (centro-bajo).
4. Saludo proactivo según hora del día con karaoke.
5. Jarvan queda en idle, esperando.

### Modo texto (sin audio)
```powershell
python cli.py
```

### Solo visual (sin Ollama ni Whisper)
```powershell
python -m ui.sphere
```

---

## 7. Controles

| Tecla / acción | Función |
|---|---|
| **Espacio** | Activa escucha (un turno) |
| **F7** | Toggle wake-word "Jarvan" (hands-free total) |
| **F8** | Toggle modo conversación continua |
| **F9** | Mute/unmute TTS (la respuesta sigue apareciendo en el HUD) |
| **Esc** | Salir |
| **Doble-click** en la esfera | Un turno |
| **Click izq** en tray icon | Un turno |
| **Click der** en tray | Menú: mostrar/ocultar componentes, salir |
| Decir "adiós" / "chao" | Despedida y cierre |

---

## 8. Comandos que entiende (ejemplos para la demo)

| Frase | Qué hace |
|---|---|
| "Buenos días" | Saludo persona (modelo rápido, sub-segundo) |
| "¿Qué hora es?" | Responde sin gastar tools — datos del SystemContext |
| "¿Qué ventanas tengo abiertas?" | Lista desde el SystemContext |
| "Abre Chrome y busca clima en Punta Arenas" | Planner → 2 pasos |
| "Pon Bohemian Rhapsody en YouTube" | Resuelve primer video real y autoplay |
| "Pausa la música" | Tecla multimedia |
| "Sube el volumen" / "Baja a la mitad" | `set_volume` con pycaw |
| "Saca una captura" | screenshot en `data/screenshots/` |
| "Lee el PDF X" | Extrae texto con pypdf |
| "Bloquea la pantalla" | LockWorkStation |
| "Adiós, Jarvan" | Se despide y cierra |

---

## 9. Tips para la presentación presencial

- **Warmup**: ejecuta `python main.py` ~2 minutos antes. Los modelos quedan en VRAM con `keep_alive: 30m` → el primer turno será rápido.
- **Demo silenciosa**: F9 muta el TTS pero el HUD karaoke sigue funcionando — útil si quieres explicar en voz mientras Jarvan "escribe".
- **Click-through**: cuando Jarvan está en idle, no bloquea ningún click. El escritorio se ve y se opera completo detrás.
- **Cierre cinematográfico**: pídele que reproduzca una canción al final → la esfera baila al ritmo del audio real saliendo de los parlantes.
- **Atajo de impacto**: lanza Jarvan con todo cerrado para que se vea solo escritorio + tres paneles HUD flotando.

---

## 10. Troubleshooting

### `pip no se reconoce` en PowerShell
PowerShell no encuentra `pip` aunque Python esté instalado. Soluciones:

1. **Usa `python -m pip` siempre** en lugar de `pip`:
   ```powershell
   python -m pip install -r requirements.txt
   ```
2. O activa el venv primero — dentro del venv, `pip` sí funciona:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

### `Activate.ps1 no se puede cargar`
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
O usa el python del venv directamente sin activar:
```powershell
.\.venv\Scripts\python.exe main.py
```

### Red bloquea pypi (proxy/firewall)
```powershell
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```
o con mirror:
```powershell
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```
o, plan B definitivo, hotspot del celular para la instalación inicial; luego Jarvan corre offline.

### `paddlepaddle-gpu` falla
No bloquea nada — el OCR cae automáticamente a tesseract.

### Ollama no responde
```powershell
ollama serve
```
en otra terminal. En Windows el instalador normalmente deja el servicio corriendo.

### Whisper no usa GPU
Verifica drivers CUDA:
```powershell
nvidia-smi
```
Si no funciona, en `config/settings.yaml`:
```yaml
stt:
  device: cpu
  compute_type: int8
```
El i9-10900X lo corre cómodo en CPU.

### VRAM agotada al cargar planner+vision a la vez
Es normal que Ollama haga swap entre ellos. Para evitarlo, en `settings.yaml` puedes bajar el planner a un modelo más liviano:
```yaml
planner_model: qwen3:8b   # ~5 GB en vez de 9
```

---

## 11. Stack técnico

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12 |
| LLM local | Ollama (qwen2.5-coder:14b, qwen3:8b, qwen2.5vl:7b, nomic-embed-text) |
| STT | faster-whisper en CUDA |
| TTS | piper (preferido), pyttsx3 (fallback con voz masculina-es) |
| Audio UI | SFX sintéticos en numpy (sin assets) |
| Visión | qwen2.5-vl como VLM principal, PaddleOCR + tesseract como OCR |
| Control de Windows | pyautogui, pywinauto, pygetwindow, pycaw |
| UI | PyQt5 (sin marco, transparente, click-through, karaoke) |
| Memoria | SQLite + ChromaDB con embeddings |
| Audio loopback | pycaw (peak meter del sistema) |
| Wake-word | openWakeWord + fallback Whisper-poll |
| Web | Playwright (headless) |
| YouTube | youtube-search-python + yt-dlp + scraping (cascada) |
| PDF | pypdf |
| Telemetría | nvidia-smi + psutil |
| Validación | pydantic v2 |
| Logging | loguru |

---

## 12. Estado del proyecto

Prototipo funcional completo. Lo que **funciona end-to-end**:

- Voz → texto → planificación → ejecución → verificación → narración → voz con karaoke.
- 24 herramientas operativas.
- Replanning automático ante fallos.
- Filler talk para nunca quedarse en silencio.
- SFX UI sincronizados con cambios de estado.
- Memoria persistente entre sesiones.
- UI completa: esfera + HUD karaoke + telemetría + contextual + tray.

Lo que **podría seguir mejorando** (futuras iteraciones):

- Voz piper neuronal en español con modelo descargado (hoy cae a pyttsx3 si no se instala).
- Vinculación con tótems del laboratorio (servidor HTTP/WebSocket replicando la esfera en pantallas remotas).
- Integración Spotify Web API.
- Tool de calendario / correo.
- Wake-word entrenado específicamente con la palabra "Jarvan".
- Visión de webcam para reconocer al usuario.

---

## 13. Créditos

 - Creado por: Duvan Figueroa Gallardo.
 - Proyecto prototipo de laboratorio.
 - Modelos de IA: Qwen (Alibaba), Whisper (OpenAI), Nomic-embed.
 - Inspiración visual y de UX: J.A.R.V.I.S. de Marvel Studios.
