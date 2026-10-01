import { useCallback, useEffect, useRef, useState } from "react";

// The Web Speech API is not in TypeScript's DOM lib; these are the few members we use.
interface SpeechAlternative {
  transcript: string;
}
interface SpeechResult {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechAlternative;
}
interface SpeechResultEvent {
  resultIndex: number;
  results: { length: number; [index: number]: SpeechResult };
}
interface SpeechErrorEvent {
  error: string;
}
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in the browser to dictate.",
  "service-not-allowed": "Microphone access was blocked. Allow it in the browser to dictate.",
  "no-speech": "No speech was heard. Try again a little closer to the microphone.",
  "audio-capture": "No microphone was found.",
  network: "Dictation needs a network connection in this browser.",
};

/**
 * Browser dictation: the text arrives in `onText` as it is spoken (interim words included), appended to whatever
 * was in the box when listening started. Nothing is sent anywhere by the app; the browser does the recognition.
 */
export function useSpeechToText(onText: (text: string) => void, lang = navigator.language || "en-US") {
  const Ctor = recognitionCtor();
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  useEffect(() => () => recognition.current?.abort(), []);

  const stop = useCallback(() => recognition.current?.stop(), []);

  const start = useCallback(
    (prefix: string) => {
      if (!Ctor || recognition.current) return;
      const rec = new Ctor();
      rec.lang = lang;
      rec.continuous = true;
      rec.interimResults = true;
      const lead = prefix.trim() ? `${prefix.trim()} ` : "";
      let finalText = "";
      rec.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) finalText += result[0].transcript;
          else interim += result[0].transcript;
        }
        onTextRef.current(`${lead}${finalText}${interim}`.replace(/\s+/g, " ").trimStart());
      };
      rec.onerror = (event) => setError(ERRORS[event.error] ?? "Dictation stopped. Try again.");
      rec.onend = () => {
        recognition.current = null;
        setListening(false);
      };
      setError(null);
      recognition.current = rec;
      setListening(true);
      rec.start();
    },
    [Ctor, lang],
  );

  return { supported: !!Ctor, listening, error, start, stop };
}
