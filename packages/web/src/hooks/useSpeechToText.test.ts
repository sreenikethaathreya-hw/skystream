import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useSpeechToText } from "@/hooks/useSpeechToText";

type Handler = ((event: unknown) => void) | null;

class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = "";
  continuous = false;
  interimResults = false;
  onresult: Handler = null;
  onerror: Handler = null;
  onend: (() => void) | null = null;
  start = vi.fn();
  stop = vi.fn(() => this.onend?.());
  abort = vi.fn();
  constructor() {
    FakeRecognition.last = this;
  }
  say(parts: { text: string; final: boolean }[]) {
    const results = parts.map((p) => Object.assign([{ transcript: p.text }], { isFinal: p.final }));
    this.onresult?.({ resultIndex: 0, results });
  }
}

afterEach(() => {
  delete (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition;
});

describe("useSpeechToText", () => {
  it("is unsupported without the Web Speech API", () => {
    const { result } = renderHook(() => useSpeechToText(() => {}));
    expect(result.current.supported).toBe(false);
  });

  it("appends interim and final words to the text that was already typed", () => {
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;
    const onText = vi.fn();
    const { result } = renderHook(() => useSpeechToText(onText, "es-ES"));

    act(() => result.current.start("Top"));
    expect(result.current.listening).toBe(true);
    const rec = FakeRecognition.last!;
    expect(rec.lang).toBe("es-ES");

    act(() => rec.say([{ text: "semillas que más", final: false }]));
    expect(onText).toHaveBeenLastCalledWith("Top semillas que más");

    act(() => rec.say([{ text: "semillas que más se venden", final: true }]));
    expect(onText).toHaveBeenLastCalledWith("Top semillas que más se venden");

    act(() => result.current.stop());
    expect(result.current.listening).toBe(false);
  });

  it("explains a blocked microphone", () => {
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = FakeRecognition;
    const { result } = renderHook(() => useSpeechToText(() => {}));
    act(() => result.current.start(""));
    act(() => FakeRecognition.last!.onerror?.({ error: "not-allowed" }));
    expect(result.current.error).toMatch(/blocked/);
  });
});
