import '../test/setup';
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Language } from '../i18n';
import { SpeechRecognitionService, recognitionLocale, type RecognitionPort } from './speechRecognition';
import { preferredVoice, SpeechSynthesisService, type SpeechUtterancePort, type SynthesisPort } from './speechSynthesis';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';

function fakeRecognition() {
  return { lang: '', interimResults: false, continuous: true, onstart: null, onresult: null, onerror: null, onend: null,
    start: vi.fn(), stop: vi.fn(), abort: vi.fn() } as unknown as RecognitionPort;
}

describe('browser speech adapters', () => {
  it.each<[Language,string]>([['en','en-IN'],['mr','mr-IN'],['hi','hi-IN']])('maps %s to %s', (language, locale) => {
    expect(recognitionLocale(language)).toBe(locale);
    const recognition = fakeRecognition();
    expect(new SpeechRecognitionService(() => recognition).createSession(language)?.lang).toBe(locale);
    expect(recognition.interimResults).toBe(true);
  });

  it('captures interim and finalized speech, then stops cleanly', () => {
    const recognition = fakeRecognition();
    const { result } = renderHook(() => useSpeechRecognition('en', new SpeechRecognitionService(() => recognition)));
    act(() => result.current.start());
    expect(result.current.status).toBe('requesting');
    act(() => recognition.onstart?.());
    expect(result.current.status).toBe('listening');
    const interim = Object.assign([{ transcript: 'Will it rain tomorrow' }], { isFinal: false });
    act(() => recognition.onresult?.({ resultIndex: 0, results: [interim] }));
    expect(result.current.interimTranscript).toBe('Will it rain tomorrow');
    const final = Object.assign([{ transcript: 'Will it rain tomorrow in Dhule?' }], { isFinal: true });
    act(() => recognition.onresult?.({ resultIndex: 0, results: [final] }));
    act(() => result.current.stop());
    expect(recognition.stop).toHaveBeenCalledOnce();
    act(() => recognition.onend?.());
    expect(result.current.status).toBe('ready');
    expect(result.current.transcript).toBe('Will it rain tomorrow in Dhule?');
  });

  it('handles permission errors, no speech, and unsupported recognition', () => {
    const recognition = fakeRecognition();
    const allowed = renderHook(() => useSpeechRecognition('mr', new SpeechRecognitionService(() => recognition)));
    act(() => allowed.result.current.start());
    act(() => recognition.onerror?.({ error: 'not-allowed' }));
    expect(allowed.result.current.error).toBe('permission');
    allowed.unmount();

    const noSpeech = renderHook(() => useSpeechRecognition('hi', new SpeechRecognitionService(() => recognition)));
    act(() => noSpeech.result.current.start());
    act(() => recognition.onend?.());
    expect(noSpeech.result.current.error).toBe('no_speech');
    noSpeech.unmount();

    const unsupported = renderHook(() => useSpeechRecognition('en', new SpeechRecognitionService(() => null)));
    act(() => unsupported.result.current.start());
    expect(unsupported.result.current.error).toBe('unsupported');
  });

  it('chooses requested-language voice and reports fallback', () => {
    const voices = [{ lang: 'en-US', name: 'English' }, { lang: 'hi-IN', name: 'Hindi' }];
    expect(preferredVoice(voices, 'hi').fallback).toBe(false);
    expect(preferredVoice(voices, 'mr').fallback).toBe(true);
    expect(preferredVoice([], 'mr').fallback).toBe(true);
  });

  it('speaks, cancels overlapping speech, stops, and handles unavailable synthesis', () => {
    const synthesis = { speaking: false, cancel: vi.fn(), speak: vi.fn(), getVoices: () => [{ lang: 'en-IN', name: 'English' }] } as unknown as SynthesisPort;
    const utterances: SpeechUtterancePort[] = [];
    const service = new SpeechSynthesisService(synthesis, (text) => {
      const utterance = { lang: '', voice: null, rate: 1, onstart: null, onend: null, onerror: null };
      (utterance as SpeechUtterancePort & { text?: string }).text = text;
      utterances.push(utterance);
      return utterance;
    });
    expect(service.speak('Dhule weather', 'en')).toMatchObject({ ok: true, fallback: false });
    expect(service.speak('Rain tomorrow', 'hi')).toMatchObject({ ok: true, fallback: true });
    expect(synthesis.cancel).toHaveBeenCalledTimes(2);
    expect(synthesis.speak).toHaveBeenCalledTimes(2);
    service.stop();
    expect(synthesis.cancel).toHaveBeenCalledTimes(3);
    expect(utterances[1].lang).toBe('hi-IN');

    expect(new SpeechSynthesisService(null, () => ({} as SpeechUtterancePort)).speak('Answer', 'en').ok).toBe(false);
    expect(service.speak('  ', 'en').ok).toBe(false);
  });
});
