# Renpho -> Garmin Connect Koerperkomposition-Sync

Holt die neueste Messung von einer Renpho-Koerperanalysewaage und schreibt
sie als Koerperkomposition (Gewicht, Koerperfett, Wasser, Muskel, viszerales
Fett, BMI, Grundumsatz, ...) nach Garmin Connect. Laeuft z.B. taeglich per
systemd-Timer nach dem morgendlichen Wiegen.

## Funktionsweise

```
[systemd Timer, z.B. taeglich 06:15]
        |
        v
renpho_to_garmin.py  ---> loggt sich bei Renpho ein, holt die neueste Messung,
                           mapped die Felder auf Garmins add_body_composition,
                           dedupliziert per Zeitstempel (renpho_sync_state.json),
                           loggt sich bei Garmin Connect ein (Token gecacht in
                           .garmin_tokens, kein taeglicher Login-Spam) und
                           schreibt die Werte
```

## Setup

```bash
pip install renpho-api garminconnect
cp renpho-to-garmin.env.example renpho-to-garmin.env
nano renpho-to-garmin.env   # RENPHO_EMAIL/PASSWORD, GARMIN_EMAIL/PASSWORD eintragen
chmod 600 renpho-to-garmin.env
```

**Erster Lauf immer mit `--dry-run`:** Renpho liefert die Messwerte als Dict,
dessen exakte Feldnamen je nach Waagen-Modell/Bibliotheksversion variieren
koennen. `--dry-run` zeigt das rohe Messobjekt UND das daraus gebaute
Garmin-Payload, ohne etwas zu schreiben - so siehst du sofort, ob z.B.
`bodyfat` wirklich so heisst, und kannst die `FIELD_MAP` im Skript in
30 Sekunden anpassen.

```bash
python3 renpho_to_garmin.py --dry-run
```

Passt die Ausgabe, normal (ohne `--dry-run`) laufen lassen:

```bash
python3 renpho_to_garmin.py
```

Bei 2FA/MFA auf dem Garmin-Konto: der allererste Login braucht interaktive
Eingabe (Code kommt per Mail/Authenticator-App). Danach wird der Session-Token
in `.garmin_tokens` gecacht - spaeter noetige (z.B. per systemd-Timer
laufende) Aufrufe brauchen dann keine erneute 2FA-Eingabe mehr, solange der
Token gueltig bleibt.

## Bekannte Stolpersteine

- **Renpho-Zeitstempel unzuverlaessig:** Das `timeStamp`-Feld mancher
  Waagen-Modelle geht 6-8 Stunden falsch (vermutlich falsch gestellte
  Waagen-Uhr). Das Skript nutzt stattdessen `localCreatedAt` (explizit lokale
  Zeit laut Renpho-Cloud) fuer den eigentlichen Garmin-Eintrag; `timeStamp`
  dient nur intern zum Sortieren/Deduplizieren.
- **EU-Region-Bug in manchen `renpho-api`-Versionen:** Falls Login/Messwerte
  fehlschlagen, kann ein bekannter Bug mit der Renpho-Region (EU vs. US-Server)
  die Ursache sein. Ein `pip install --upgrade renpho-api` kann einen lokal
  gepatchten Fix in `renpho/client.py` zuruecksetzen - nach jedem Upgrade
  kurz mit `--dry-run` gegenpruefen.
- **Garmin-Rate-Limiting:** Zu viele Logins pro Tag fuehren zu
  `GarminConnectTooManyRequestsError` (429). Der Token-Cache (`.garmin_tokens`)
  ist genau dafuer da - nicht loeschen, sonst wird bei jedem Lauf neu
  eingeloggt.

## systemd-Einrichtung

`systemd/renpho-to-garmin.service` und `.timer` als Vorlage (Pfade auf euer
System anpassen), dann:

```bash
sudo cp systemd/renpho-to-garmin.service systemd/renpho-to-garmin.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now renpho-to-garmin.timer
```

## Telegram-Benachrichtigungen (optional)

`notify_telegram.sh` + `systemd/renpho-alert.service` schicken bei
Fehlschlag (`OnFailure=` in der `.service`-Datei) und/oder nach jedem
erfolgreichen Lauf (`ExecStartPost=`) eine Telegram-Nachricht. Setup:

```bash
cp notify.env.example notify.env
nano notify.env   # TELEGRAM_TOKEN (via @BotFather) und TELEGRAM_CHAT_ID (via @userinfobot)
chmod 600 notify.env
```

## Lizenz

MIT, siehe LICENSE.
