from kokoro import KPipeline
import soundfile as sf
import matplotlib.pyplot as plt
import numpy as np

pipeline = KPipeline(lang_code='f',repo_id='hexgrad/Kokoro-82M')

text = "Salut Damien ! C'est ton premier test avec Kokoro v1.0 en 2026. Est-ce que ma voix sonne naturelle ? On va essayer avec une voix sympa."

generator = pipeline(text, voice='af_bella')

for i, (gs, ps, audio) in enumerate(generator):
    filename = f"kokoro_test_{i}.wav"
    sf.write(filename, audio, 24000)
    print(f"Audio généré et sauvegardé : {filename}")

    plt.figure(figsize=(10, 4))
    plt.plot(np.arange(len(audio)) / 24000.0, audio)
    plt.title(f"Waveform - Voice: af_heart")
    plt.xlabel("Temps (secondes)")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.show()