# Phase 9: Voice interaction and conversational accessibility

Voice is an optional interface to the existing chat. The microphone button
starts one browser-native `SpeechRecognition` session after an explicit user
action. Recognition uses the Phase 7 language selection (`en-IN`, `mr-IN`, or
`hi-IN`) and puts finalized text in the regular chat input for review and
editing. Sending it uses the existing `POST /api/v1/chat` request and routing.
Interim text is shown as a listening preview and is not inserted in the input.

Assistant messages have a read-aloud control backed by browser
`SpeechSynthesis`. Starting another message replaces current playback, and
each message can stop its own playback. The selected language is used as the
utterance locale; a browser voice for that locale is used when available, with
the browser's default voice as fallback. Playback remains optional and never
starts automatically.

The frontend does not store or upload raw microphone audio. Browser speech
recognition availability and its processing/privacy behavior depend on the
browser and its speech service. Browsers without the Web Speech recognition
API retain normal text chat. Speech playback also depends on browser support
and installed voices; unavailable playback leaves the text response intact.

Validation commands:

```powershell
cd backend
python -m pytest -q
cd ../frontend
npm test
npm run build
```
