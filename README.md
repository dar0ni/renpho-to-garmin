# Intervals Coach

Ein selbstgebauter, automatischer Trainings- und Ernährungscoach für Ausdauersport.
Er läuft rund um die Uhr auf einem Raspberry Pi, zieht sich deine Daten aus
[intervals.icu](https://intervals.icu), rechnet Form und Belastung aus und
schickt dir einen Tagesreport über Telegram. Optional lässt sich das Ganze so
erweitern, dass du direkt aus der **Claude App** heraus mit deinen Trainingsdaten
arbeiten kannst.

Das Projekt ist aus dem persönlichen Setup eines Hobby-Radsportlers entstanden
und bewusst so aufgebaut, dass andere es nachbauen und an ihre eigene Sportart,
ihren Standort und ihre Ziele anpassen können.

> **Wichtig vorab:** Das ist ein Hobby-Projekt, kein medizinisches Gerät und keine
> Trainingsberatung im rechtlichen Sinn. Alle Empfehlungen, Kalorien- und
> Belastungswerte sind Richtwerte. Du trainierst und isst auf eigene Verantwortung.
> Bei gesundheitlichen Fragen sprich mit einem Arzt oder qualifizierten Trainer.

---

## Was kann das Ding?

- **Tagesreport** mit Form (CTL/ATL/TSB), Wellness (HRV, Ruhepuls, Schlaf) und einer Trainingsempfehlung
- **Analyse einzelner Einheiten** aus den Rohdaten (Normalized Power, Intensity Factor, TSS, aerobes Decoupling, Peak-Leistungen)
- **Ernährungslogging** per Text oder Barcode-Scan, mit Tagesbilanz und Makro-Zielen
- **Windanalyse** einer Fahrt anhand der GPS-Spur und stündlicher Wetterdaten
- **Kalender-Anbindung**, damit die Planung deinen Schichtrhythmus berücksichtigt
- **Direktzugriff aus der Claude App** über einen MCP-Server (optionaler Ausbau)

---

## Wie es aufgebaut ist

Das Projekt besteht aus zwei Programmen, die unabhängig voneinander laufen:

| Programm | systemd-Dienst | Aufgabe |
|---|---|---|
| `coach.py` | `intervals-coach.service` | Telegram-Bot, Tagesreport, Ernährungslog, Kalender |
| `mcp_server.py` | `pi-coach-mcp.service` | Schnittstelle für die Claude App (optionaler Ausbau) |

`coach.py` ist das Fundament und funktioniert für sich allein. `mcp_server.py`
baut darauf auf und importiert Funktionen aus `coach.py`. Wenn dir der
Telegram-Bot reicht, kannst du den zweiten Teil einfach weglassen.

Datenquellen: **intervals.icu** ist die Hauptquelle, **Strava** kann ergänzend
genutzt werden. Wetter kommt von **Open-Meteo** (kostenlos, kein Schlüssel nötig).

---

## Voraussetzungen

**Hardware:** Ein Raspberry Pi (getestet auf einem Pi 5, ältere gehen auch) mit
Raspberry Pi OS. Ein normaler Linux-Rechner tut es zum Ausprobieren genauso.

**Accounts, die du brauchst:**

- Ein **intervals.icu**-Konto (kostenlos). Deine Uhr sollte dorthin synchronisieren, zum Beispiel über Garmin Connect oder Strava.
- Ein **Telegram**-Konto für den Bot.
- Optional ein **Google**-Konto, wenn du die Kalender-Anbindung willst.
- Optional ein **Anthropic**-Konto mit der Claude App für den MCP-Ausbau.

**Vorkenntnisse:** Du solltest dich per SSH auf den Pi verbinden und einfache
Kommandos in ein Terminal tippen können. Programmieren musst du nicht.

---

## Teil 1: Basis-Setup (Telegram-Bot)

Das ist der Kern. Wenn du hier durch bist, läuft dein Coach.

### 1. Projekt holen und Umgebung einrichten

```bash
git clone https://github.com/<DEIN_HANDLE>/intervals-coach.git
cd intervals-coach

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Das `venv` ist eine abgekapselte Python-Umgebung, damit die Pakete des Projekts
nicht mit dem System-Python kollidieren.

### 2. intervals.icu API-Schlüssel und Athlete-ID

Deinen API-Schlüssel findest du auf intervals.icu unter **Settings**, ganz unten
im Abschnitt **Developer**. Kopiere den Schlüssel.

Deine Athlete-ID steht in der Adresszeile, wenn du dein Profil öffnest. Sie sieht
aus wie `i12345`.

### 3. Telegram-Bot erstellen

Öffne in Telegram den Chat mit **@BotFather**, schicke `/newbot` und folge den
Fragen. Am Ende bekommst du einen **Token**, der so ähnlich aussieht wie
`123456789:ABCdef...`. Den brauchst du gleich.

Jetzt fehlt noch deine **Chat-ID**, damit der Bot weiß, wohin er schreiben soll.
Schreibe deinem neuen Bot irgendeine Nachricht, dann öffne im Browser:

```
https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates
```

In der Antwort steht bei `"chat":{"id": ...}` deine Chat-ID (eine Zahl).

### 4. Konfiguration ausfüllen

Kopiere die Vorlage und öffne sie in einem Editor:

```bash
cp config/config.example.json config/config.json
nano config/config.json
```

Trage deine Werte ein: `intervals_api_key`, `athlete_id`, `athlete_ftp`,
`telegram_token`, `telegram_chat_id`. Setze `weather_lat`, `weather_lon` und
`weather_location_name` auf deinen Ort (die Koordinaten findest du zum Beispiel
über eine Kartenseite). Die E-Mail- und Claude-Felder kannst du leer lassen oder
auf den Platzhaltern stehen lassen, wenn du diese Funktionen nicht nutzt.

> **Merke:** `config/config.json` enthält deine Geheimnisse und ist bewusst über
> `.gitignore` vom Hochladen ausgeschlossen. Trage hier niemals Zugangsdaten ein,
> die du später committen würdest.

### 5. Google Kalender anbinden (optional)

Wenn du willst, dass die Planung deinen Kalender kennt, brauchst du einmalig ein
Google-Token. Das ist der fummeligste Schritt, deshalb Schritt für Schritt:

1. Öffne die [Google Cloud Console](https://console.cloud.google.com), lege ein Projekt an.
2. Aktiviere darin die **Google Calendar API**.
3. Erstelle unter **APIs & Dienste → Anmeldedaten** einen **OAuth-Client-ID** vom Typ **Desktop-App**.
4. Lade die JSON herunter und speichere sie als `config/credentials.json`.
5. Führe an einem Rechner **mit Browser** einmalig aus:

```bash
python generate_token.py
```

Es öffnet sich ein Browserfenster, du meldest dich an und bestätigst den
Lesezugriff auf deinen Kalender. Danach liegt `config/token.json` bereit.

Läuft dein Pi headless, also ohne Bildschirm, dann mach diesen Schritt auf deinem
Laptop und kopiere anschließend `config/token.json` per `scp` auf den Pi.

### 6. Erster Test

```bash
python coach.py
```

Der Bot sollte starten und dir in Telegram die Befehlsübersicht schicken. Tippe
dort `/status` oder `/morgen`, um zu sehen, ob die Daten ankommen. Zum Beenden
`Strg+C`.

### 7. Als Dauerdienst einrichten

Damit der Bot dauerhaft und nach jedem Neustart läuft, legst du einen
systemd-Dienst an. Erstelle `/etc/systemd/system/intervals-coach.service`:

```ini
[Unit]
Description=Intervals Coach Telegram Bot
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/intervals-coach
ExecStart=/home/pi/intervals-coach/venv/bin/python /home/pi/intervals-coach/coach.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Pfade und `User` an dein System anpassen. Dann aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now intervals-coach.service
sudo systemctl status intervals-coach.service
```

Logs anschauen kannst du jederzeit mit `journalctl -u intervals-coach -f`.

**Damit ist der Basis-Teil fertig.** Alles Weitere ist Kür.

---

## Teil 2: Ausbau mit MCP-Server und Claude App (fortgeschritten)

Dieser Teil macht den Coach über die **Claude App** ansprechbar, sodass du im
Chat direkt deine Trainingsdaten analysieren und Events schreiben kannst. Er ist
deutlich anspruchsvoller, weil ein eigener Server erreichbar gemacht werden muss.
Wenn dir der Telegram-Bot reicht, überspring das hier.

### 1. Tailscale einrichten

Dein Pi braucht eine sichere, öffentlich erreichbare Adresse für die
MCP-Verbindung. Am einfachsten geht das mit [Tailscale](https://tailscale.com)
und dessen Funnel-Funktion, die einen einzelnen Port nach außen freigibt.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Notiere dir die Adresse deines Pi im Tailnet, sie sieht aus wie
`https://dein-pi.deintailnet.ts.net`. Diese Adresse trägst du oben in
`mcp_server.py` bei `PUBLIC_URL` und in der `allowed_hosts`-Liste ein, damit der
Server nur unter deiner eigenen Adresse antwortet.

### 2. Ein eigenes API-Token vergeben

In `config/config.json` steht das Feld `api_server_token`. Setze dort ein
selbst ausgedachtes, langes Zufallstoken. Es schützt deinen MCP-Server.

### 3. MCP-Server als Dienst

Analog zum Bot, in `/etc/systemd/system/pi-coach-mcp.service`:

```ini
[Unit]
Description=Pi Coach MCP Server
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/intervals-coach
ExecStart=/home/pi/intervals-coach/venv/bin/python /home/pi/intervals-coach/mcp_server.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pi-coach-mcp.service
```

Danach die Funnel-Freigabe für den MCP-Port setzen (der Server lauscht per Default
auf Port 8766):

```bash
sudo tailscale funnel 8766
```

Ob der Server lebt, prüfst du über den Health-Endpunkt:

```bash
curl https://dein-pi.deintailnet.ts.net/health
```

Kommt `{"status":"ok",...}` zurück, steht der Server.

### 4. In der Claude App verbinden

In der Claude App fügst du unter den Einstellungen einen **benutzerdefinierten
Connector** hinzu und gibst die MCP-Adresse deines Pi an
(`https://dein-pi.deintailnet.ts.net/mcp`). Der Server bringt einen einfachen
OAuth-Ablauf mit, der die Verbindung für genau einen Nutzer freigibt. Danach
stehen dir die Coach-Werkzeuge direkt im Chat zur Verfügung.

---

## Tests

Das Projekt bringt Tests für die Kernberechnungen mit (Form-Deprojektion,
Normalized Power, Ernährungs- und Zonen-Parsing). So läuft es:

```bash
venv/bin/python -m pip install pytest
venv/bin/python -m pytest test_coach.py -v
```

Wichtig ist, die Tests mit dem Python aus dem `venv` zu starten, damit alle
Pakete gefunden werden. Nach Änderungen an den Rechenfunktionen zeigen dir die
Tests sofort, ob etwas kaputtgegangen ist.

---

## Projektstruktur

```
intervals-coach/
├── coach.py                    # Hauptprogramm: Bot, Report, Ernährung, Kalender
├── mcp_server.py               # MCP-Server für die Claude App (optional)
├── test_coach.py               # Tests der Kernberechnungen
├── generate_token.py           # Einmaliges Google-Kalender-Setup
├── requirements.txt            # Python-Abhängigkeiten
├── README.md                   # diese Anleitung
├── LICENSE                     # MIT-Lizenz
├── .gitignore                  # schützt Geheimnisse und persönliche Daten
└── config/
    └── config.example.json     # Vorlage für deine config.json
```

Dateien, die **nicht** im Repo liegen und die du selbst anlegst:
`config/config.json`, `config/credentials.json`, `config/token.json` sowie zur
Laufzeit `oauth_store.json`, `nutrition_logs/` und `logs/`. Sie enthalten
Geheimnisse oder persönliche Daten und sind über `.gitignore` ausgeschlossen.

---

## Sicherheit

- Trage Zugangsdaten ausschließlich in `config/config.json` ein, niemals direkt in den Code.
- Lade niemals `config.json`, `credentials.json`, `token.json` oder `oauth_store.json` hoch. Die `.gitignore` verhindert das, solange du sie nicht überschreibst.
- Wenn ein Schlüssel doch einmal öffentlich geworden ist, stelle ihn sofort neu aus. Bei intervals.icu und Telegram geht das mit wenigen Klicks.

---

## Lizenz

MIT. Nutzung, Änderung und Weitergabe sind frei, siehe `LICENSE`. Ohne
Gewährleistung. Das Projekt trifft keine medizinischen Aussagen.
