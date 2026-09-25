# Multilingual chat and interface

WeatherGPT Phase 7 supports English (`en`), Marathi (`mr`), and Hindi (`hi`).
English is the default. The UI language selector stores the choice in browser
`localStorage` under `weathergpt-language`; no account or device location is
needed.

The frontend sends chat language as an optional `language` field alongside the
original user message. Existing clients may omit it and continue to receive
English. The backend validates the supported language codes. Forecast, current
weather, alert, and advisory provider schemas remain language-independent; only
intent normalization and human-readable presentation are localized. Provider
names, source attribution, measurements, dates, warning colors, and warning
codes remain unchanged.

The localization implementation lives in `frontend/src/i18n/` and
`backend/app/services/localization_service.py`. Marathi and Hindi chat routing
normalizes common weather phrases to the existing English intent route. Static
UI strings use small frontend dictionaries. Localized chat presentation uses
deterministic templates over the canonical response; the existing local LLM
advisory phrasing prompt also receives an explicit language instruction. If
that LLM request fails, the existing deterministic advisory summary remains in
use. Untranslated static phrases safely fall back to English.

Run backend tests from `backend` with `python -m pytest -q`; run frontend tests
from `frontend` with `npm test`; create a production build with `npm run build`.
