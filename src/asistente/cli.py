import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="asistente")
    sub = parser.add_subparsers(dest="comando")
    hablar_p = sub.add_parser("hablar", help="decir un texto en voz alta")
    hablar_p.add_argument("texto")
    transcribir_p = sub.add_parser("transcribir", help="transcribir un archivo de audio")
    transcribir_p.add_argument("archivo", type=Path)
    sub.add_parser("diagnosticar", help="medir micrófono, activación y fin de frase")
    sub.add_parser("voces", help="escuchar las voces masculinas en español")
    vigilar_p = sub.add_parser("microfono", help="vigilar el micrófono y el cambio de dispositivo")
    vigilar_p.add_argument("--segundos", type=float, default=60)
    args = parser.parse_args()

    if args.comando == "microfono":
        from .diagnostico import vigilar_microfono

        try:
            vigilar_microfono(args.segundos)
        except KeyboardInterrupt:
            pass
    elif args.comando == "diagnosticar":
        from .diagnostico import diagnosticar

        diagnosticar()
    elif args.comando == "voces":
        from .diagnostico import probar_voces

        probar_voces()
    elif args.comando == "hablar":
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
