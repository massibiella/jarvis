// Singleton audio graph shared by mic input and TTS playback so the Orb
// visualizer can read live amplitude/frequency data without routing audio
// buffers through React state (which would repaint on every frame).
class AudioEngine {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private micSource: MediaStreamAudioSourceNode | null = null;
  private micStream: MediaStream | null = null;
  private elementSource: MediaElementAudioSourceNode | null = null;
  private freqData: Uint8Array<ArrayBuffer> | null = null;

  private ensureContext(): { ctx: AudioContext; analyser: AnalyserNode } {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.75;
      this.freqData = new Uint8Array(new ArrayBuffer(this.analyser.frequencyBinCount));
    }
    if (this.ctx.state === "suspended") {
      void this.ctx.resume();
    }
    return { ctx: this.ctx, analyser: this.analyser! };
  }

  async connectMic(): Promise<void> {
    const { ctx, analyser } = this.ensureContext();
    if (this.micSource) return;
    this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.micSource = ctx.createMediaStreamSource(this.micStream);
    this.micSource.connect(analyser);
  }

  disconnectMic(): void {
    this.micSource?.disconnect();
    this.micSource = null;
    this.micStream?.getTracks().forEach((track) => track.stop());
    this.micStream = null;
  }

  connectElement(el: HTMLAudioElement): void {
    const { ctx, analyser } = this.ensureContext();
    if (this.elementSource) {
      this.elementSource.disconnect();
    }
    this.elementSource = ctx.createMediaElementSource(el);
    this.elementSource.connect(analyser);
    this.elementSource.connect(ctx.destination);
  }

  /** Returns a snapshot of frequency-bin amplitudes (0-255), or null if no audio graph exists yet. */
  getFrequencyData(): Uint8Array | null {
    if (!this.analyser || !this.freqData) return null;
    this.analyser.getByteFrequencyData(this.freqData);
    return this.freqData;
  }

  /** Average amplitude across all bins, normalized to 0-1. */
  getLevel(): number {
    const data = this.getFrequencyData();
    if (!data) return 0;
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    return sum / data.length / 255;
  }
}

export const audioEngine = new AudioEngine();
