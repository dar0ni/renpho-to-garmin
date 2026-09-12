#!/usr/bin/env python3
"""
renpho_to_garmin.py — holt die neueste Renpho-Körperanalysemessung und
schreibt sie in Garmin Connect (Körperkomposition: Gewicht, Körperfett,
Wasser, Muskel, viszerales Fett, BMI, ...).

Setup auf dem Pi:
    pip install renpho-api garminconnect

Credentials NICHT im Skript, sondern als Umgebungsvariablen (z.B. via
systemd EnvironmentFile mit chmod 600), siehe renpho-to-garmin.env.example:
    RENPHO_EMAIL, RENPHO_PASSWORD   -> Renpho-App-Login
    GARMIN_EMAIL, GARMIN_PASSWORD   -> Garmin-Connect-Login

Erster Lauf IMMER mit --dry-run starten: Renpho liefert die Messwerte als
Dict, dessen exakte Feldnamen ich nicht 1:1 verifizieren konnte (Bibliothek
ist noch jung). --dry-run zeigt das rohe Messobjekt UND das daraus gebaute
Garmin-Payload, ohne etwas zu schreiben — damit siehst du sofort, ob z.B.
"bodyfat" wirklich so heißt oder z.B. "body_fat_percentage", und kannst die
FIELD_MAP unten in 30 Sekunden korrigieren.

Danach normal (ohne --dry-run) laufen lassen, z.B. täglich per systemd-Timer
nach dem morgendlichen Wiegen. Ein State-File verhindert Doppel-Uploads.
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "renpho_sync_state.json")
TOKEN_STORE = os.path.join(SCRIPT_DIR, ".garmin_tokens")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def _load_dotenv(path):
    """Liest eine .env-Datei OHNE die Shell (kein 'source' nötig, keine
    Verstuemmelung von Passwoertern mit $, #, Leerzeichen, Quotes etc.).
    Setzt eine Variable nur, wenn sie nicht schon in der Umgebung steckt
    (z.B. via systemd EnvironmentFile), damit dieser Fallback nichts
    ueberschreibt, was schon korrekt gesetzt ist."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            os.environ.setdefault(key, val)


_load_dotenv(os.path.join(SCRIPT_DIR, "renpho-to-garmin.env"))

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "renpho_to_garmin.log"),
    level=logging.INFO,
    format="%(asctime)s [renpho2garmin] %(levelname)s %(message)s",
)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# Renpho-Feldname -> Garmin add_body_composition-Parametername.
# Per --dry-run am 2026-09-10 gegen echte Messdaten verifiziert.
FIELD_MAP = {
    "weight":       "weight",
    "bodyfat":      "percent_fat",
    "water":        "percent_hydration",
    "bone":         "bone_mass",
    "muscle":       "muscle_mass",
    "bmr":          "basal_met",
    "visfat":       "visceral_fat_rating",
    "bmi":          "bmi",
    "bodyage":      "metabolic_age",
}


def build_garmin_payload(measurement: dict) -> dict:
    payload = {}
    for renpho_key, garmin_key in FIELD_MAP.items():
        val = measurement.get(renpho_key)
        if val is not None:
            payload[garmin_key] = val
    return payload


def load_last_synced_ts():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f).get("last_ts")
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_last_synced_ts(ts):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_ts": ts}, f)


def main():
    parser = argparse.ArgumentParser(description="Renpho -> Garmin Connect Körperkomposition-Sync")
    parser.add_argument("--dry-run", action="store_true",
                         help="Nur anzeigen was übertragen würde, nichts schreiben.")
    args = parser.parse_args()

    try:
        renpho_email = os.environ["RENPHO_EMAIL"]
        renpho_password = os.environ["RENPHO_PASSWORD"]
    except KeyError as e:
        logging.error("Fehlende Umgebungsvariable: %s", e)
        sys.exit(1)

    from renpho import RenphoClient
    renpho = RenphoClient(renpho_email, renpho_password)
    renpho.login()
    measurements = renpho.get_all_measurements()
    if not measurements:
        logging.info("Keine Renpho-Messungen gefunden.")
        return

    # Sortierschlüssel für den Zeitstempel je nach tatsächlichem Feldnamen
    # (time_stamp / timestamp / date) robust wählen.
    def _ts(m):
        # "timeStamp" (camelCase) ist das tatsaechliche Renpho-Feld;
        # die anderen bleiben als Fallback fuer andere Scale-Typen.
        for k in ("timeStamp", "time_stamp", "timestamp", "date", "time"):
            if k in m and m[k] is not None:
                return m[k]
        return 0

    latest = sorted(measurements, key=_ts)[-1]
    ts = _ts(latest)

    if args.dry_run:
        print("\n--- Rohes Renpho-Messobjekt ---")
        print(json.dumps(latest, indent=2, default=str, ensure_ascii=False))
        print("\n--- Daraus gebautes Garmin-Payload (FIELD_MAP) ---")
        print(json.dumps(build_garmin_payload(latest), indent=2, ensure_ascii=False))
        print("\nFeldnamen oben mit der Ausgabe abgleichen, FIELD_MAP im Skript ggf. anpassen.")
        print("Kein Schreibvorgang in diesem Modus (--dry-run).")
        return

    last_synced = load_last_synced_ts()
    if last_synced and ts and ts <= last_synced:
        logging.info("Neueste Messung (%s) bereits synchronisiert, nichts zu tun.", ts)
        return

    try:
        garmin_email = os.environ["GARMIN_EMAIL"]
        garmin_password = os.environ["GARMIN_PASSWORD"]
    except KeyError as e:
        logging.error("Fehlende Umgebungsvariable: %s", e)
        sys.exit(1)

    import garminconnect

    # Session-Token cachen (Datei), damit nicht bei jedem Cron-Lauf neu
    # eingeloggt werden muss (Garmin blockt bei zu vielen Logins/Tag).
    # login(TOKEN_STORE) versucht zuerst den gecachten Token zu laden und
    # speichert nach einem (Fallback-)Login mit Email/Passwort automatisch
    # dorthin. Der Fallback greift hier nur, wenn wirklich kein Token da ist
    # und keine MFA noetig ist (fuer MFA: einmalig garmin_login_setup.py).
    try:
        garmin = garminconnect.Garmin()
        garmin.login(TOKEN_STORE)
    except Exception:
        garmin = garminconnect.Garmin(garmin_email, garmin_password)
        garmin.login(TOKEN_STORE)

    # Garmins add_body_composition erwartet eine NAIVE lokale Zeit (kein UTC,
    # keine Konvertierung intern). Renphos "timeStamp"-Epoch ist unzuverlaessig
    # (bei diesem Scale-Modell ca. 6-8h Abweichung zur echten Ortszeit - vermutlich
    # falsch gestellte Waagen-Uhr). "localCreatedAt" ist dagegen explizit lokale
    # Zeit laut Renpho-Cloud und wird deshalb direkt uebernommen, ohne jede
    # Zeitzonen-Umrechnung. timeStamp bleibt nur fuers Sortieren/Dedup oben.
    local_str = latest.get("localCreatedAt")
    if local_str:
        local_dt_str = local_str.replace(" ", "T", 1)
    else:
        local_dt_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        logging.warning("Kein localCreatedAt im Messobjekt, nutze aktuelle Systemzeit als Fallback.")

    payload = build_garmin_payload(latest)
    if "weight" not in payload:
        logging.error("Kein Gewichtswert im Messobjekt gefunden, breche ab. Rohdaten: %s", latest)
        sys.exit(1)

    garmin.add_body_composition(timestamp=local_dt_str, **payload)

    save_last_synced_ts(ts)
    logging.info("Renpho-Messung vom %s (lokale Zeit laut Renpho) nach Garmin übertragen: %s",
                 local_dt_str, payload)


if __name__ == "__main__":
    main()
