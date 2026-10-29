import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="asistente")
    sub = parser.add_subparsers(dest="comando")
    hablar_p = sub.add_parser("hablar", help="decir un texto en voz alta")
    hablar_p.add_argument("texto")
    transcribir_p = sub.add_parser("transcribir", help="transcribir un archivo de audio")
    transcribir_p.add_argument("archivo", type=Path)
    args = parser.parse_args()

    if args.comando == "hablar":
        from .tts import hablar

        hablar(args.texto)
    elif args.comando == "transcribir":
        from .stt import transcribir_archivo

        print(transcribir_archivo(args.archivo))
    else:
        from .loop import ejecutar

        try:
            ejecutar()
        except KeyboardInterrupt:
            pass
