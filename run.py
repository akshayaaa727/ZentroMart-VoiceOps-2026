
import sys
from pathlib import Path

from voice_agent import VoiceAgent, voice_turn


def main():
    if len(sys.argv) != 2:
        print("Usage: python run.py <audio_folder>")
        sys.exit(1)

    audio_folder = Path(sys.argv[1])

    if not audio_folder.is_dir():
        print("Error: Audio folder does not exist.")
        sys.exit(1)

    output_folder = Path("sample_outputs")
    output_folder.mkdir(exist_ok=True)

    extensions = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac"}
    audio_files = sorted(
        p for p in audio_folder.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    )

    if not audio_files:
        print("No supported audio files found.")
        sys.exit(1)

    agent = VoiceAgent()

    for audio_file in audio_files:
        print(f"\nProcessing: {audio_file.name}")

        try:
            result_folder = output_folder / audio_file.stem
            result_folder.mkdir(exist_ok=True)

            heard, reply = voice_turn(
                str(audio_file),
                agent,
                output_file=str(result_folder / "reply.wav"),
            )

            (result_folder / "transcript.txt").write_text(
                heard, encoding="utf-8"
            )

            (result_folder / "reply.txt").write_text(
                reply, encoding="utf-8"
            )

            evidence_text = "\n\n".join(
                f"{i}. {item['source']} — "
                f"{item.get('heading', 'Knowledge-base section')}\n"
                f"{item['text']}"
                for i, item in enumerate(agent.last_evidence, 1)
            )

            (result_folder / "retrieved_evidence.txt").write_text(
                evidence_text or "No RAG evidence retrieved for this turn.",
                encoding="utf-8",
            )

            print(f"Saved outputs to {result_folder}")

        except Exception as exc:
            print(f"Failed to process {audio_file.name}: {exc}")


if __name__ == "__main__":
    main()

