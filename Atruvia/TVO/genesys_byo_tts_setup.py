#!/usr/bin/env python3
"""Create + configure a Genesys Cloud BYO TTS (genesys-tts-connector) integration."""
import json, os, sys, requests

# ---------- Configuration (env vars) ----------
REGION         = os.getenv("GC_REGION", "mypurecloud.de")          # e.g. mypurecloud.com, mypurecloud.de
CLIENT_ID      = os.environ["GC_CLIENT_ID"]
CLIENT_SECRET  = os.environ["GC_CLIENT_SECRET"]

INTEGRATION_NAME = os.getenv("INTEGRATION_NAME", "ElevenLabs TTS Connector")
MODEL_ID       = os.getenv("MODEL_ID", "eleven_v3")
VOICE_ID       = os.getenv("VOICE_ID", "")                          # empty -> selectable in Architect ($voice)
OUTPUT_FORMAT_MAPPING = json.loads(os.getenv("OUTPUT_FORMAT_MAPPING", '{"audio/L16":{"*":"pcm_8000"}}'))
LANGUAGE_MAPPING      = json.loads(os.getenv("LANGUAGE_MAPPING", '{"de-de":"de","en-us":"en"}'))

CREDENTIAL_ID  = os.getenv("CREDENTIAL_ID", "")                     # reuse existing credential if set
TTS_API_KEY    = os.getenv("TTS_API_KEY", "")
CRED_FIELDS    = {"userName": os.getenv("TTS_USER", "xi-api-key"), "password": TTS_API_KEY}

API = f"https://api.{REGION}"


def token():
    r = requests.post(f"https://login.{REGION}/oauth/token",
                      data={"grant_type": "client_credentials"},
                      auth=(CLIENT_ID, CLIENT_SECRET))
    r.raise_for_status()
    return r.json()["access_token"]


S = requests.Session()
S.headers.update({"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})


def call(method, path, body=None):
    r = S.request(method, API + path, json=body)
    if not r.ok:
        sys.exit(f"{method} {path} -> {r.status_code}: {r.text}")
    return r.json() if r.text else {}


# 1) Create integration
integ = call("POST", "/api/v2/integrations", {
    "name": INTEGRATION_NAME,
    "integrationType": {"id": "genesys-tts-connector"},
})
iid = integ["id"]
print("Integration:", iid)

# 2) Credential
if not CREDENTIAL_ID:
    cred = call("POST", "/api/v2/integrations/credentials", {
        "name": f"{INTEGRATION_NAME} credential",
        "type": {"name": "basicAuth"},
        "credentialFields": CRED_FIELDS,
    })
    CREDENTIAL_ID = cred["id"]
print("Credential:", CREDENTIAL_ID)

# 3) Get current version
current = call("GET", f"/api/v2/integrations/{iid}/config/current")

# 4) Put config
voice_path = VOICE_ID if VOICE_ID else "$voice"
config = {
    "name": INTEGRATION_NAME,
    "version": current["version"],
    "properties": {
        "ttsConnectorVoicesURI": "https://api.elevenlabs.io/v1/voices",
        "ttsConnectorSynthesizeURI": f"https://api.elevenlabs.io/v1/text-to-speech/{voice_path}/stream",
        "ttsConnectorSynthesizeMethod": "post",
        "voicesAttribute": "voices",
        "voiceIdAttribute": "voice_id",
        "voiceNameAttribute": "name",
        "voiceTypeAttribute": "type",
        "voiceLanguageAttribute": "fine_tuning|language",
        "voiceGenderAttribute": "labels|gender",
        "synthesizeVoiceAttribute": "voice",
        "synthesizeTextAttribute": "text",
        "synthesizeTypeAttribute": "output_format",
        "synthesizeRateAttribute": "samplerate",
        "synthesizeLanguageAttribute": "language",
        "isPciCompliant": True,
    },
    "advanced": {
        "synthesizeBody": {
            "text": "$text",
            "model_id": MODEL_ID,
            "optimize_streaming_latency": 3,
            "apply_text_normalization": "on",
        },
        "outputFormatMapping": OUTPUT_FORMAT_MAPPING,
        "voiceMapping": {"languageMapping": LANGUAGE_MAPPING},
    },
    "notes": "",
    "credentials": {"basicAuth": {"id": CREDENTIAL_ID}},
}
call("PUT", f"/api/v2/integrations/{iid}/config/current", config)
print("Config saved.")

# 5) Enable
call("PATCH", f"/api/v2/integrations/{iid}", {"intendedState": "ENABLED"})
print("Enabled. Done ->", iid)
