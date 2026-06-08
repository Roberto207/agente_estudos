#!/usr/bin/env python3
"""
Setup interativo — cria o config.yaml a partir do template.
Execute: python setup.py
"""
import os
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    console = Console()
except ImportError:
    print("Rich não instalado. Execute: pip install rich")
    sys.exit(1)

TEMPLATE = Path("config.example.yaml")
TARGET = Path("config.yaml")


def main():
    console.print("\n[bold purple]Agente Estudos — Setup[/bold purple]\n")

    if not TEMPLATE.exists():
        console.print("[red]config.example.yaml não encontrado. Execute na pasta raiz do projeto.[/red]")
        sys.exit(1)

    if TARGET.exists():
        if not Confirm.ask(f"[yellow]{TARGET} já existe. Sobrescrever?[/yellow]", default=False):
            console.print("Setup cancelado.")
            return

    providers = {
        "1": ("anthropic", "Anthropic (Claude)", "ANTHROPIC_API_KEY"),
        "2": ("openai",    "OpenAI (GPT-4o)",    "OPENAI_API_KEY"),
        "3": ("groq",      "Groq (LLaMA)",        "GROQ_API_KEY"),
        "4": ("ollama",    "Ollama (local)",       None),
    }

    console.print("Escolha o provider de LLM:")
    for k, (_, label, _) in providers.items():
        console.print(f"  [{k}] {label}")

    choice = Prompt.ask("Provider", choices=list(providers.keys()), default="1")
    provider, label, env_var = providers[choice]

    api_key = ""
    if env_var:
        api_key = os.environ.get(env_var, "")
        if api_key:
            console.print(f"[green]✓ Usando chave de {env_var}[/green]")
        else:
            api_key = Prompt.ask(f"[blue]{label} API Key[/blue]", password=True)

    ollama_url = "http://localhost:11434"
    if provider == "ollama":
        ollama_url = Prompt.ask("Ollama URL", default="http://localhost:11434")
        model = Prompt.ask("Modelo Ollama", default="llama3.2:latest")
    elif provider == "anthropic":
        model = Prompt.ask("Modelo", default="claude-opus-4-8")
    elif provider == "openai":
        model = Prompt.ask("Modelo", default="gpt-4o")
    elif provider == "groq":
        model = Prompt.ask("Modelo", default="llama-3.3-70b-versatile")

    # Transcrição
    console.print("\n[blue]Configuração de transcrição de vídeo local:[/blue]")
    console.print("  [auto] Tenta Groq Whisper, depois local, depois pula")
    console.print("  [groq] Usa API Whisper do Groq (recomendado)")
    console.print("  [local] Usa openai-whisper local")
    console.print("  [none] Pula transcrição de arquivos locais")
    transcription = Prompt.ask("Provider de transcrição", choices=["auto", "groq", "local", "none"], default="auto")

    groq_for_transcription = ""
    if transcription == "groq" and provider != "groq":
        groq_for_transcription = Prompt.ask("Groq API Key para transcrição", password=True, default="")

    # Monta o YAML
    config_lines = [
        f"provider: {provider}",
        "",
        "anthropic:",
        f'  api_key: "{api_key if provider == "anthropic" else ""}"',
        f'  model: "{model if provider == "anthropic" else "claude-opus-4-8"}"',
        "",
        "openai:",
        f'  api_key: "{api_key if provider == "openai" else ""}"',
        f'  model: "{model if provider == "openai" else "gpt-4o"}"',
        "",
        "groq:",
        f'  api_key: "{api_key if provider == "groq" else ""}"',
        f'  model: "{model if provider == "groq" else "llama-3.3-70b-versatile"}"',
        "",
        "ollama:",
        f'  base_url: "{ollama_url}"',
        f'  model: "{model if provider == "ollama" else "llama3.2:latest"}"',
        "",
        "transcription:",
        f"  provider: {transcription}",
        f'  groq_api_key: "{groq_for_transcription}"',
        '  local_model: "base"',
        "",
        "search:",
        "  max_results: 5",
    ]

    TARGET.write_text("\n".join(config_lines) + "\n", encoding="utf-8")
    console.print(f"\n[green]✓ {TARGET} criado com sucesso![/green]")
    console.print("\nPróximos passos:")
    console.print("  python main.py --tema 'Redes Neurais' --foco 'backpropagation' --pasta ~/obsidian/redes_neurais")
    console.print("  python main.py --interactive  # modo interativo")


if __name__ == "__main__":
    main()
